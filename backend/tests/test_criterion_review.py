"""Criterion-level adjudication preserves raw evidence and explicit trust boundaries."""
import copy
import csv
import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models import TrainingSession, Audit
from conftest import assign, start, send


def finished(env):
    session = start(env)
    sid = session['id']
    send(env, sid, 'card_opened')
    response = env['student'].post(f'/api/sessions/{sid}/submit', json={})
    assert response.status_code == 200, response.text
    return response.json()


def decide(env, sid, cid, status='pass', comment='Факт проверен преподавателем', **extra):
    return env['teacher'].post(f'/api/sessions/{sid}/criterion-reviews', json={
        'criterion_id':cid, 'status':status, 'comment':comment, **extra})


def test_expert_decision_preserves_original_report(env):
    before = finished(env)
    original = before['report']
    criterion = next(c for c in original['criteria'] if c['id'].startswith('fact:'))
    sid = before['id']
    snapshot = env['teacher'].get(f'/api/sessions/{sid}').json()['scenario_snapshot']
    response = decide(env, sid, criterion['id'])
    assert response.status_code == 200, response.text
    after = response.json()['report']
    for key,value in original.items():
        assert after[key] == value
    assert after['criterion_reviews'][criterion['id']]['status'] == 'pass'
    assert after['expert_assessment']['score'] == original['score'] + criterion['max_points']
    assert after['criterion_reviews'][criterion['id']]['evidence_ids'] == criterion['evidence_ids']
    assert after['criterion_review_revision'] == 1
    assert after['teacher_review_stale'] is False
    assert env['teacher'].get(f'/api/sessions/{sid}').json()['scenario_snapshot'] == snapshot
    assert env['student'].get(f'/api/sessions/{sid}').json()['report'] == after


def test_stale_and_partial_adjudication_not_trusted():
    from app.recommendations import trusted_score
    assert trusted_score({'score':80,'requires_review':False,'teacher_review_stale':True}) is None
    pending = {'score':80,'requires_review':False,'criterion_review_revision':1,
               'criterion_reviews':{'fact:address':{'status':'pass','comment':'Проверено'}}}
    assert trusted_score(pending) is None


def confirm(env, sid, score=90, revision=0):
    response = env['teacher'].post(f'/api/sessions/{sid}/review', json={
        'score':score,'comment':'Общий результат проверен','expected_criterion_revision':revision})
    assert response.status_code == 200, response.text
    return response.json()


def test_repeat_decision_append_only_and_overall_becomes_stale(env):
    session = finished(env);sid = session['id'];cid = session['report']['criteria'][0]['id']
    first = decide(env,sid,cid).json()
    assert first['report']['criterion_reviews'][cid]['revision'] == 1
    reviewed = confirm(env,sid,score=92,revision=1)
    assert reviewed['status'] == 'reviewed'
    second = decide(env,sid,cid,'fail','После разбора подтверждено нарушение',expected_criterion_revision=1).json()
    report = second['report']
    assert second['status'] == 'submitted'
    assert report['teacher_review'] == reviewed['report']['teacher_review']
    assert report['teacher_review_stale'] is True
    assert report['criterion_review_revision'] == 2
    events = [e for e in second['events'] if e['kind']=='criterion_review_saved']
    assert len(events) == 2
    assert events[0]['payload']['previous'] is None
    assert events[1]['payload']['previous'] == first['report']['criterion_reviews'][cid]
    assert events[1]['payload']['current'] == report['criterion_reviews'][cid]
    from app.recommendations import trusted_score
    assert trusted_score(report) is None
    final = confirm(env,sid,score=86,revision=2)
    assert final['report']['teacher_review_stale'] is False
    assert final['report']['teacher_review']['criterion_revision'] == 2
    assert trusted_score(final['report']) == 86
    final_events = [e for e in final['events'] if e['kind']=='review_saved']
    assert final_events[-1]['payload']['previous_review']['score'] == 92
    with env['app'].state.session_factory() as db:
        audit = list(db.scalars(select(Audit).where(Audit.entity_id==sid,Audit.action=='criterion_review_saved')))
        assert len(audit) == 2
        assert {a.details['revision'] for a in audit} == {1,2}
        assert all('comment' not in a.details for a in audit)


def test_reposting_identical_criterion_decision_preserves_confirmed_review(env):
    session = finished(env); sid = session['id']; cid = session['report']['criteria'][0]['id']
    first = decide(env, sid, cid).json()
    confirmed = confirm(env, sid, score=91, revision=1)
    duplicate = decide(env, sid, cid, expected_criterion_revision=1)
    assert duplicate.status_code == 200, duplicate.text
    assert duplicate.json() == confirmed
    assert duplicate.json()['report']['criterion_review_revision'] == first['report']['criterion_review_revision']
    assert duplicate.json()['report']['teacher_review_stale'] is False
    assert len([e for e in duplicate.json()['events'] if e['kind']=='criterion_review_saved']) == 1


@pytest.mark.parametrize('endpoint', ['review','criterion-reviews'])
@pytest.mark.parametrize('expected', [None,0,2])
def test_stale_tabs_cannot_confirm_or_change_unseen_revision(env,endpoint,expected):
    session = finished(env);sid = session['id'];cid = session['report']['criteria'][0]['id']
    before = decide(env,sid,cid).json()
    body = {'score':90,'comment':'Подтверждение из старой вкладки'} if endpoint=='review' else {'criterion_id':cid,'status':'fail','comment':'Решение из старой вкладки'}
    if expected is not None: body['expected_criterion_revision'] = expected
    result = env['teacher'].post(f'/api/sessions/{sid}/{endpoint}',json=body)
    assert result.status_code == 409, result.text
    after = env['teacher'].get(f'/api/sessions/{sid}').json()
    assert after == before


def test_criterion_access_and_active_conflicts(env):
    session = start(env);sid = session['id']
    assert decide(env,sid,'anything').status_code == 409
    session = env['student'].post(f'/api/sessions/{sid}/submit',json={}).json()
    cid = session['report']['criteria'][0]['id']
    body = {'criterion_id':cid,'status':'pass','comment':'Неверная роль'}
    for role in ['student','admin']:
        assert env[role].post(f'/api/sessions/{sid}/criterion-reviews',json=body).status_code == 403
    assert env['public'].post(f'/api/sessions/{sid}/criterion-reviews',json=body).status_code == 401
    env['admin'].post('/api/admin/users',json={'username':'foreign_reviewer','name':'Другой преподаватель','password':'OtherPass112!','role':'teacher'})
    with TestClient(env['app']) as other:
        other.post('/api/auth/login',json={'username':'foreign_reviewer','password':'OtherPass112!'})
        assert other.post(f'/api/sessions/{sid}/criterion-reviews',json=body).status_code == 403


@pytest.mark.parametrize('body', [
    {'criterion_id':'invented'}, {'status':'pending'}, {'comment':'   '}, {'comment':' я '},
    {'comment':'x'*2000}, {'evidence_ids':['unknown-event']}, {'evidence_ids':['x','x']},
    {'evidence_ids':[str(i) for i in range(51)]}, {'score':100}, {'expected_criterion_revision':-1},
])
def test_invalid_decisions_are_rejected_without_report_or_history_change(env,body):
    session = finished(env);sid = session['id'];cid = session['report']['criteria'][0]['id']
    before = env['teacher'].get(f'/api/sessions/{sid}').json()
    payload = {'criterion_id':cid,'status':'pass','comment':'Содержательное основание',**body}
    response = env['teacher'].post(f'/api/sessions/{sid}/criterion-reviews',json=payload)
    assert response.status_code == 422, response.text
    assert env['teacher'].get(f'/api/sessions/{sid}').json() == before


def test_foreign_evidence_rejected_and_selected_own_evidence_preserved(env):
    first = finished(env);second = finished(env)
    sid = first['id'];cid = first['report']['criteria'][0]['id']
    assert decide(env,sid,cid,evidence_ids=[second['events'][0]['id']]).status_code == 422
    own = first['events'][0]['id']
    response = decide(env,sid,cid,comment='   Факт проверен   ',evidence_ids=[own])
    assert response.status_code == 200, response.text
    decision = response.json()['report']['criterion_reviews'][cid]
    assert decision['comment'] == 'Факт проверен' and decision['evidence_ids'] == [own]


def test_default_evidence_over_limit_requires_explicit_selection(env):
    session = start(env);sid = session['id']
    for i in range(51):
        assert send(env,sid,'status_changed',{'status':'accepted','comment':f'Учебное действие {i}'}).status_code == 200
    finished = env['student'].post(f'/api/sessions/{sid}/submit',json={}).json()
    workflow = next(c for c in finished['report']['criteria'] if c['id']=='workflow')
    assert len(workflow['evidence_ids']) == 51
    before = env['teacher'].get(f'/api/sessions/{sid}').json()
    assert decide(env,sid,'workflow').status_code == 422
    assert env['teacher'].get(f'/api/sessions/{sid}').json() == before
    selected = workflow['evidence_ids'][:50]
    response = decide(env,sid,'workflow',evidence_ids=selected)
    assert response.status_code == 200, response.text
    assert response.json()['report']['criterion_reviews']['workflow']['evidence_ids'] == selected


def test_effective_summary_is_pure_and_zero_weight_review_stays_visible():
    from app.expert_review import effective_criteria, expert_summary
    report = {'score':0,'max_score':100,'requires_review':True,'criteria':[
        {'id':'fact:address','status':'review','points':0,'max_points':20,'critical':True,'evidence_ids':['old']},
        {'id':'grammar','status':'review','points':0,'max_points':0,'critical':False}],
        'criterion_reviews':{'fact:address':{'status':'pass','evidence_ids':['new']}}}
    original = copy.deepcopy(report)
    assert expert_summary(report) == {'score':20,'max_score':100,'requires_review':True,'critical_errors':0}
    effective = effective_criteria(report)
    assert effective[0]['status'] == 'pass' and effective[0]['evidence_ids'] == ['new']
    effective[0]['evidence_ids'].append('mutation')
    assert report == original
    report['criterion_reviews']['fact:address']['status'] = 'fail'
    assert expert_summary(report)['critical_errors'] == 1


def test_explicit_facts_only_trusted_after_current_confirmation():
    from app.expert_review import trusted_score, trusted_criteria
    report = {'score':50,'requires_review':True,'criterion_review_revision':2,'criteria':[
        {'id':'fact:address','status':'review','max_points':20},
        {'id':'fact:dispatch','status':'fail','max_points':20},
        {'id':'grammar','status':'review','max_points':0}],
        'criterion_reviews':{'fact:address':{'status':'pass'},'grammar':{'status':'fail'}}}
    assert trusted_criteria(report) == []
    report['teacher_review'] = {'score':90,'comment':'Общий результат подтверждён','criterion_revision':1}
    assert trusted_score(report) is None
    report['teacher_review']['criterion_revision'] = 2
    assert {c['id'] for c in trusted_criteria(report)} == {'fact:address'}
    report['teacher_review_stale'] = True
    assert trusted_criteria(report) == []


def test_three_corrected_attempts_only_explicit_failure_forms_weak_skill():
    from types import SimpleNamespace as Obj
    from app.recommendations import recommend
    rows = []
    for i in range(3):
        report = {'score':20,'requires_review':True,'criterion_review_revision':1,
            'teacher_review':{'score':90,'comment':'Общий итог проверен','criterion_revision':1},
            'criteria':[{'id':'fact:address','title':'Адрес','status':'review','max_points':20},
                        {'id':'fact:dispatch','title':'Направление','status':'fail','max_points':20,'critical':True}],
            'criterion_reviews':{'fact:address':{'status':'fail'}}}
        rows.append(Obj(id=str(i),status='reviewed',finished_at=str(i),snapshot={'service':'Учебная ДДС'},report=report))
    result = recommend(Obj(id='student',name='Ученик',service='Учебная ДДС'),rows,set(),[])
    assert result['sample_size'] == 3 and result['average_score'] == 90
    assert result['criterion_evidence_attempts'] == 3
    assert [c['criterion_id'] for c in result['weak_skills']] == ['fact:address']
    assert result['weak_skills'][0]['failed'] == 3
    # The unadjudicated critical dispatch failure must not force basic.
    assert result['proposed_level'] == 'intermediate'
    rows[0].report['teacher_review_stale'] = True
    result = recommend(Obj(id='student',name='Ученик',service='Учебная ДДС'),rows,set(),[])
    assert result['sample_size'] == 2 and result['proposed_level'] is None


def test_rc1_criteria_keep_old_trust_policy_and_teacher_review_can_reopen_fact():
    from app.expert_review import trusted_criteria
    report = {'score':80,'requires_review':False,'criteria':[{'id':'fact:address','status':'fail','max_points':20}]}
    assert len(trusted_criteria(report)) == 1
    report['teacher_review'] = {'score':80,'comment':'Подтверждено'}
    assert len(trusted_criteria(report)) == 1
    report['teacher_review']['score'] = 90
    assert trusted_criteria(report) == []
    report['teacher_review']['score'] = 80
    report['criterion_reviews'] = {'fact:address':{'status':'review'}}
    assert trusted_criteria(report) == []


def test_analytics_recommendations_exclude_stale_and_stopped_even_after_final(env):
    session = finished(env);sid = session['id'];cid = session['report']['criteria'][0]['id']
    # RC1: a definite automatic result is eligible until criterion adjudication begins.
    assert session['report']['requires_review'] is False
    assert env['teacher'].get('/api/analytics').json()['scored_sessions'] == 1
    decide(env,sid,cid)
    assert env['teacher'].get('/api/analytics').json()['scored_sessions'] == 0
    confirm(env,sid,revision=1)
    analytics = env['teacher'].get('/api/analytics').json()
    assert analytics['scored_sessions'] == 1 and analytics['average_score'] == 90
    assert {c['id'] for c in analytics['criteria']} == {cid}
    recommendations = env['teacher'].get('/api/recommendations').json()['items'][0]
    assert recommendations['sample_size'] == 1
    decide(env,sid,cid,'fail',expected_criterion_revision=1)
    assert env['teacher'].get('/api/analytics').json()['scored_sessions'] == 0
    assert env['teacher'].get('/api/recommendations').json()['items'][0]['sample_size'] == 0
    confirm(env,sid,revision=2)
    stopped = start(env);stopid = stopped['id']
    stopped = env['teacher'].post(f'/api/sessions/{stopid}/stop',json={}).json()
    stopcid = stopped['report']['criteria'][0]['id']
    assert decide(env,stopid,stopcid).status_code == 200
    confirm(env,stopid,score=100,revision=1)
    analytics = env['teacher'].get('/api/analytics').json()
    assert analytics['scored_sessions'] == 1 and analytics['average_score'] == 90
    assert analytics['completed_sessions'] == 1
    assert env['teacher'].get('/api/recommendations').json()['items'][0]['evidence_session_ids'] == [sid]


def test_analytics_keeps_reused_criterion_ids_with_different_titles_separate(env):
    first = finished(env);second = finished(env)
    cid = first['report']['criteria'][0]['id']
    original_title = first['report']['criteria'][0]['title']
    with env['app'].state.session_factory() as db:
        row = db.get(TrainingSession,second['id'])
        report = copy.deepcopy(row.report)
        report['criteria'][0]['title'] = 'Переименованный учебный критерий'
        row.report = report
        db.commit()
    aggregate = [c for c in env['teacher'].get('/api/analytics').json()['criteria'] if c['id']==cid]
    assert {(c['title'],c['total']) for c in aggregate} == {
        (original_title,1),('Переименованный учебный критерий',1)}


def test_analytics_exposes_sample_counts_and_ranks_confirmed_gaps(env):
    finished_rows = [finished(env) for _ in range(3)]
    pending = finished(env)
    pending_cid = pending['report']['criteria'][0]['id']
    assert decide(env, pending['id'], pending_cid).status_code == 200
    stopped = start(env)
    assert env['teacher'].post(f"/api/sessions/{stopped['id']}/stop", json={}).status_code == 200
    assign(env)
    start(env)

    outcomes = [
        [('a', 'Адрес', 'fail'), ('b', 'Связь', 'fail'), ('c', 'Решение', 'fail')],
        [('a', 'Адрес', 'fail'), ('b', 'Связь', 'fail')],
        [('a', 'Адрес', 'pass')],
    ]
    with env['app'].state.session_factory() as db:
        for session, criteria in zip(finished_rows, outcomes):
            row = db.get(TrainingSession, session['id'])
            report = copy.deepcopy(row.report)
            report['requires_review'] = False
            report['score'] = 50
            report['criteria'] = [
                {'id': cid, 'title': title, 'status': status, 'max_points': 10}
                for cid, title, status in criteria
            ]
            row.report = report
        db.commit()

    result = env['teacher'].get('/api/analytics').json()
    assert {key: result[key] for key in (
        'total_sessions', 'completed_sessions', 'scored_sessions',
        'stopped_sessions', 'pending_review_sessions', 'active_sessions',
    )} == {
        'total_sessions': 7, 'completed_sessions': 4, 'scored_sessions': 3,
        'stopped_sessions': 1, 'pending_review_sessions': 1, 'active_sessions': 1,
    }
    assert [(c['id'], c['failed'], c['total']) for c in result['criteria']] == [
        ('b', 2, 2), ('a', 2, 3), ('c', 1, 1),
    ]


def test_csv_keeps_original_effective_and_formula_safe_reason(env):
    session = finished(env);sid = session['id'];criterion = session['report']['criteria'][0]
    reason = '=SUM(1;2)\n"Учебное основание"'
    decision = decide(env,sid,criterion['id'],'fail',reason)
    assert decision.status_code == 200
    text = env['student'].get(f'/api/sessions/{sid}/export.csv').text
    rows = list(csv.reader(io.StringIO(text.lstrip('\ufeff')),delimiter=';'))
    headers = rows[2]
    row = next(r for r in rows[3:] if r[0]==criterion['title'])
    assert row[headers.index('Исход')] == criterion['status']
    assert row[headers.index('Эффективный исход')] == 'fail'
    assert row[headers.index('Основание решения')] == "'" + reason
    assert 'Общий итог устарел' in rows[0]


def test_ai_never_reconsiders_definite_expert_decision():
    from app.ai import review_semantics, SemanticReview, ReviewSuggestion
    from app.config import Settings
    report = {'criteria':[
        {'id':'fact:address','title':'Адрес','status':'review','category':'content','expected':'Адрес'},
        {'id':'fact:dispatch','title':'Направление','status':'review','category':'content','expected':'Направление'}],
        'criterion_reviews':{'fact:address':{'status':'pass'}}}
    original = copy.deepcopy(report)
    answer = SemanticReview(suggestions=[
        ReviewSuggestion(criterion_id='fact:address',observation='Не отменять преподавателя',quote='Адрес'),
        ReviewSuggestion(criterion_id='fact:dispatch',observation='Уточнить направление',quote='Адрес')])
    events = [{'kind':'trainee_message','payload':{'text':'Адрес'}}]
    with patch('app.ai.completion',return_value=(answer,.1)) as model:
        result = review_semantics(Settings(),{'card':{},'reference_response':''},events,report)
        data = model.call_args.args[2]
        assert [c['id'] for c in data['criteria']] == ['fact:dispatch']
    assert [s['criterion_id'] for s in result['suggestions']] == ['fact:dispatch']
    assert result['discarded_unsupported'] == 1 and report == original
    report['criterion_reviews']['fact:dispatch'] = {'status':'fail'}
    with patch('app.ai.completion') as model:
        result = review_semantics(Settings(),{},[],report)
    model.assert_not_called()
    assert result['mode'] == 'not_requested'
