from copy import deepcopy
from types import SimpleNamespace as Obj
import pytest
from fastapi.testclient import TestClient
from app.models import TrainingSession, Event, Scenario, now
from app.recommendations import recommend
from app.routes.recommendations import router
from conftest import assign


def criterion(status='pass', critical=False):
    return {'id':'workflow','title':'Действия с карточкой','status':status,'max_points':25,'critical':critical}


def attempt(i, score=100, requires_review=False, **kwargs):
    return Obj(id=f'attempt-{i}',status=kwargs.get('status','submitted'),finished_at=f'2026-09-19T10:{i:02d}:00+00:00',snapshot={'service':kwargs.get('service','Мосводоканал')},report={'score':score,'requires_review':requires_review,'teacher_review':kwargs.get('teacher_review'),'criteria':kwargs.get('criteria',[criterion()])})


STUDENT=Obj(id='student',name='Учебный участник',service='Мосводоканал')
SCENARIOS=[Obj(id='water-basic',data={'title':'Вода','service':'Мосводоканал','difficulty':'basic'}),Obj(id='water-advanced',data={'title':'Полный цикл','service':'Мосводоканал','difficulty':'advanced'}),Obj(id='lift-advanced',data={'title':'Лифт','service':'Мослифт','difficulty':'advanced'})]


def test_insufficient_and_uncertain_attempts_do_not_assign_level():
    rows=[attempt(1),attempt(2),attempt(3,requires_review=True),attempt(4,status='stopped'),attempt(5,status='active'),attempt(6,service='Мослифт')]
    result=recommend(STUDENT,rows,set(),SCENARIOS)
    assert result['sample_size']==2 and result['proposed_level'] is None
    assert result['status']=='insufficient_data' and result['weak_skills']==[]
    assert result['teacher_decides'] and result['suggested_scenarios']==[]


def test_three_confirmed_high_scores_suggest_compatible_advanced():
    result=recommend(STUDENT,[attempt(i) for i in range(3)],set(),SCENARIOS)
    assert result['proposed_level']=='advanced' and result['average_score']==100
    assert result['evidence_session_ids']==['attempt-2','attempt-1','attempt-0']
    assert [s['id'] for s in result['suggested_scenarios']]==['water-advanced']
    assert result['classroom']['student_service']=='Мосводоканал'
    assert result['suggested_scenarios'][0]['selection_basis']=='profile_level'
    assert result['suggested_scenarios'][0]['matched_criteria']==[]
    assert result['unmatched_criteria']==[] and 'по профилю' in result['scenario_selection_reason']


def test_repeated_criterion_failure_has_counts_and_only_failed_evidence():
    rows=[attempt(1,70,criteria=[criterion('fail')]),attempt(2,80,criteria=[criterion('fail')]),attempt(3,100)]
    result=recommend(STUDENT,rows,set(),SCENARIOS)
    assert result['proposed_level']=='intermediate'
    assert result['weak_skills']==[{'criterion_id':'workflow','title':'Действия с карточкой','failed':2,'total':3,'failure_rate':.667,'evidence_session_ids':['attempt-2','attempt-1']}]


def test_critical_error_and_low_mean_propose_basic():
    critical=[attempt(1,90,criteria=[criterion('fail',True)]),attempt(2),attempt(3)]
    assert recommend(STUDENT,critical,set(),SCENARIOS)['proposed_level']=='basic'
    assert recommend(STUDENT,[attempt(i,59) for i in range(3)],set(),SCENARIOS)['proposed_level']=='basic'
    assert recommend(STUDENT,[attempt(i,60) for i in range(3)],set(),SCENARIOS)['proposed_level']=='intermediate'
    assert recommend(STUDENT,[attempt(i,85) for i in range(3)],set(),SCENARIOS)['proposed_level']=='advanced'


def test_teacher_review_accepts_score_without_fabricating_criterion_adjudication():
    rows=[attempt(i,40,requires_review=True,teacher_review={'score':90,'comment':'Перефраз принят'},criteria=[criterion('fail',True)]) for i in range(3)]
    result=recommend(STUDENT,rows,set(),SCENARIOS)
    assert result['sample_size']==3 and result['average_score']==90
    assert result['weak_skills']==[] and result['criterion_evidence_attempts']==0
    assert 'без подтверждения отдельных критериев' in result['reason']
    assert recommend(STUDENT,rows,{'attempt-1'},SCENARIOS)['proposed_level'] is None


def test_recent_window_and_invalid_scores_are_transparent():
    rows=[attempt(i,100 if i>=3 else 0) for i in range(13)]
    result=recommend(STUDENT,rows,set(),SCENARIOS)
    assert result['eligible_count']==13 and result['sample_size']==10
    assert result['average_score']==100 and 'attempt-0' not in result['evidence_session_ids']
    for bad in [float('nan'),float('inf'),True,-1,101,'100']:
        assert recommend(STUDENT,[attempt(1,bad)],set(),SCENARIOS)['sample_size']==0


def mounted(env):
    app=env['app']
    if not any(getattr(r,'path',None)=='/api/recommendations' for r in app.routes):
        # Root integrates main separately; test this router before the frontend catchall.
        old=len(app.router.routes);app.include_router(router,prefix='/api')
        additions=app.router.routes[old:];del app.router.routes[old:]
        app.router.routes[0:0]=additions


def store_finished(env,score=100,teacher_id=None,student_id=None,stopped=False):
    scenario=next(s for s in env['teacher'].get('/api/scenarios').json() if s['service']=='Мосводоканал')
    row=assign(env,student_id=student_id,scenario_id=scenario['id'])
    with env['app'].state.session_factory() as db:
        item=db.get(TrainingSession,row['id']);item.status='reviewed' if stopped else 'submitted';item.finished_at=now()
        if teacher_id:item.teacher_id=teacher_id
        item.report={'score':score,'requires_review':False,'teacher_review':{'score':score,'comment':'Подтверждено'} if stopped else None,'criteria':[criterion()]}
        if stopped:db.add(Event(session_id=item.id,kind='teacher_stopped',payload={},sequence=1))
        db.commit()
    return row['id']


def test_api_roles_scope_stopped_after_review_and_no_mutations(env):
    mounted(env)
    assert env['public'].get('/api/recommendations').status_code==401
    assert env['admin'].get('/api/recommendations').status_code==403
    teacher=env['teacher'];student=env['student']
    assert teacher.get('/api/recommendations').json()['items']==[]
    assert student.get('/api/recommendations').json()['items'][0]['status']=='insufficient_data'
    good=[store_finished(env) for _ in range(3)]
    stopped=store_finished(env,stopped=True)
    new=env['admin'].post('/api/admin/users',json={'username':'teacher_other','name':'Другой преподаватель','role':'teacher','password':'OtherPass112!'}).json()
    foreign=store_finished(env,score=10,teacher_id=new['id'])
    other=TestClient(env['app'])
    try:
        assert other.post('/api/auth/login',json={'username':'teacher_other','password':'OtherPass112!'}).status_code==200
        other_result=other.get('/api/recommendations').json()['items'][0]
        assert other_result['sample_size']==1 and other_result['evidence_session_ids']==[foreign]
        teacher_result=teacher.get('/api/recommendations').json()['items'][0]
        assert set(teacher_result['evidence_session_ids'])==set(good)
        assert stopped not in teacher_result['evidence_session_ids'] and foreign not in teacher_result['evidence_session_ids']
        before=student.get('/api/sessions').json()
        result=student.get('/api/recommendations').json()
        after=student.get('/api/sessions').json()
        assert before==after
        assert result['teacher_decides'] and result['items'][0]['sample_size']==4
        encoded=str(result)
        for private in ['expected_statuses','required_facts','reference_response','password_hash','snapshot']:
            assert private not in encoded
    finally:other.close()


def test_student_does_not_see_another_student_history(env):
    mounted(env)
    other=next(u for u in env['teacher'].get('/api/users').json() if u['username']=='student_water')
    foreign=store_finished(env,student_id=other['id'])
    result=env['student'].get('/api/recommendations').json()['items']
    assert len(result)==1 and result[0]['sample_size']==0
    assert foreign not in str(result)


def test_arrival_failure_does_not_recommend_dispatch_only_scenario():
    arrival={'id':'arrival','label':'Прибытие бригады подтверждено','patterns':['Бригада прибыла']}
    rows=[attempt(i,50,criteria=[{'id':'fact:arrival','title':arrival['label'],'status':'fail','max_points':35,'critical':True}]) for i in range(3)]
    for row in rows:
        row.snapshot['required_facts']=[arrival]
    dispatch=Obj(id='dispatch-only',data={'title':'Отключение воды в учебном доме','service':'Мосводоканал','difficulty':'basic',
        'required_facts':[{'id':'dispatch','label':'Направление бригады подтверждено','patterns':['Бригада направлена']}]})
    result=recommend(STUDENT,rows,set(),[dispatch])
    assert result['suggested_scenarios']==[]
    assert result['unmatched_criteria']==[{'criterion_id':'fact:arrival','title':arrival['label']}]


ARRIVAL={'id':'arrival','label':'Прибытие бригады подтверждено','patterns':['Бригада прибыла']}
DISPATCH={'id':'dispatch','label':'Направление бригады подтверждено','patterns':['Бригада направлена']}
CONTACT={'id':'duty','name':'Дежурный','phone':'2001','role':'Должностное лицо','greeting':'Слушаю','reply':'Бригада прибыла'}


def fact_failures(facts):
    criteria=[{'id':'fact:'+fact['id'],'title':fact['label'],'status':'fail','max_points':35,'critical':True} for fact in facts]
    rows=[attempt(i,50,criteria=deepcopy(criteria)) for i in range(3)]
    for row in rows:
        row.snapshot.update(required_facts=deepcopy(facts),contacts=[deepcopy(CONTACT)])
    return rows


def basic_scenario(sid, facts, title=None, **data):
    return Obj(id=sid,data={'title':title or sid,'service':'Мосводоканал','difficulty':'basic',
        'required_facts':deepcopy(facts),'contacts':[deepcopy(CONTACT)],**data})


def test_fact_match_requires_both_id_and_label_and_reports_partial_coverage():
    rows=fact_failures([ARRIVAL,DISPATCH])
    scenarios=[basic_scenario('same-id-different-label',[{**ARRIVAL,'label':'Выезд бригады'}]),
        basic_scenario('same-label-different-id',[{**ARRIVAL,'id':'other'}]),basic_scenario('correct',[ARRIVAL])]
    result=recommend(STUDENT,rows,set(),scenarios)
    assert [s['id'] for s in result['suggested_scenarios']]==['correct']
    assert result['suggested_scenarios'][0]['matched_criteria']==[{'criterion_id':'fact:arrival','title':ARRIVAL['label']}]
    assert result['suggested_scenarios'][0]['selection_basis']=='rubric_match'
    assert result['unmatched_criteria']==[{'criterion_id':'fact:dispatch','title':DISPATCH['label']}]
    assert '1 из 2' in result['scenario_selection_reason']


@pytest.mark.parametrize('missing_source',[None,{'service':'Мосводоканал'},
    {'service':'Мосводоканал','required_facts':[{**ARRIVAL,'label':'Другой смысл'}]},
    {'service':'Мосводоканал','required_facts':[ARRIVAL,ARRIVAL]}])
def test_unverifiable_failing_snapshot_cannot_support_fact_match(missing_source):
    rows=fact_failures([ARRIVAL]);rows[0].snapshot=missing_source
    # Universal profile keeps an absent snapshot eligible for the score policy;
    # it must still never supply evidence of what the failed criterion meant.
    student=Obj(id='student',name='Участник',service='Учебная ДДС')
    result=recommend(student,rows,set(),[basic_scenario('candidate',[ARRIVAL])])
    assert result['sample_size']==3 and result['suggested_scenarios']==[]
    assert result['unmatched_criteria']==[{'criterion_id':'fact:arrival','title':ARRIVAL['label']}]


def test_contact_confirmation_required_by_any_failed_snapshot_is_preserved():
    rows=fact_failures([ARRIVAL])
    rows[0].snapshot['required_facts'][0]['confirmed_by_contact_ids']=['duty']
    gated={**ARRIVAL,'confirmed_by_contact_ids':['other-duty']}
    scenarios=[basic_scenario('weakened',[ARRIVAL]),
        basic_scenario('broken-link',[gated]),
        basic_scenario('valid',[gated],contacts=[{**CONTACT,'id':'other-duty'}])]
    result=recommend(STUDENT,rows,set(),scenarios)
    assert [s['id'] for s in result['suggested_scenarios']]==['valid']
    assert result['unmatched_criteria']==[]
    rows[0].snapshot['contacts']=[]
    assert recommend(STUDENT,rows,set(),scenarios)['suggested_scenarios']==[]


def test_successful_snapshot_does_not_add_a_causal_requirement_to_failed_criteria():
    rows=fact_failures([ARRIVAL])
    rows[0].report['criteria'][0]['status']='pass'
    rows[0].snapshot['required_facts'][0]['confirmed_by_contact_ids']=['duty']
    result=recommend(STUDENT,rows,set(),[basic_scenario('valid',[ARRIVAL])])
    assert result['weak_skills'][0]['failed']==2
    assert [s['id'] for s in result['suggested_scenarios']]==['valid']


def test_confirmation_link_requires_a_callable_contact_with_a_script():
    fact={**ARRIVAL,'confirmed_by_contact_ids':['duty']}
    rows=fact_failures([fact])
    scenarios=[basic_scenario('no-reply',[fact],contacts=[{**CONTACT,'reply':''}]),
        basic_scenario('ambiguous-phone',[fact],contacts=[CONTACT,{**CONTACT,'id':'duplicate-phone'}]),
        basic_scenario('valid',[fact])]
    assert [s['id'] for s in recommend(STUDENT,rows,set(),scenarios)['suggested_scenarios']]==['valid']


@pytest.mark.parametrize('field,value',[
    ('patterns',[]),('confirmed_by_contact_ids','duty'),('confirmed_by_contact_ids',['duty','duty']),
    ('confirmed_by_contact_ids',['unknown']),
])
def test_malformed_candidate_fact_is_not_explained_as_practice(field,value):
    result=recommend(STUDENT,fact_failures([ARRIVAL]),set(),[basic_scenario('broken',[{**ARRIVAL,field:value}])])
    assert result['suggested_scenarios']==[]


@pytest.mark.parametrize('cid,title,field,value,bad',[
    ('reaction','Открытие карточки','response_limit_seconds',30,True),
    ('duration','Первый статус с текстом','completion_limit_seconds',180,0),
    ('workflow','Действия с карточкой','expected_statuses',['accepted','responding'],['not-a-status']),
    ('outgoing_call','Исходящий доклад должностному лицу','contacts',[CONTACT],[{**CONTACT,'phone':'invalid'}]),
])
def test_builtin_matches_require_fixed_title_and_real_conditions_in_both_snapshots(cid,title,field,value,bad):
    rows=[attempt(i,50,criteria=[{'id':cid,'title':title,'status':'fail','max_points':25,'critical':True}]) for i in range(3)]
    for row in rows:row.snapshot[field]=deepcopy(value)
    valid=basic_scenario('valid',[],**{field:value})
    invalid=basic_scenario('invalid',[],**{field:bad})
    result=recommend(STUDENT,rows,set(),[invalid,valid])
    assert [s['id'] for s in result['suggested_scenarios']]==['valid']
    rows[0].snapshot[field]=bad
    assert recommend(STUDENT,rows,set(),[valid])['suggested_scenarios']==[]
    for row in rows:
        row.snapshot[field]=value
        row.report['criteria'][0]['title']='Подменённое название'
    assert recommend(STUDENT,rows,set(),[valid])['suggested_scenarios']==[]


def test_unknown_criterion_does_not_gain_match_from_title_or_scenario_name():
    rows=[attempt(i,50,criteria=[{'id':'custom','title':'Понятность ручного текста','status':'fail','max_points':5,'critical':False}]) for i in range(3)]
    result=recommend(STUDENT,rows,set(),[basic_scenario('candidate',[ARRIVAL],title='Понятность ручного текста')])
    assert result['suggested_scenarios']==[]
    assert result['unmatched_criteria']==[{'criterion_id':'custom','title':'Понятность ручного текста'}]


def test_matches_rank_before_alphabetic_order_then_title_and_id():
    scenarios=[basic_scenario('z-both',[ARRIVAL,DISPATCH],title='Я'),
        basic_scenario('b-one',[ARRIVAL],title='А'),basic_scenario('a-one',[ARRIVAL],title='А')]
    result=recommend(STUDENT,fact_failures([ARRIVAL,DISPATCH]),set(),scenarios)
    assert [s['id'] for s in result['suggested_scenarios']]==['z-both','a-one','b-one']
    assert result['unmatched_criteria']==[]


def test_unmatched_criteria_are_computed_from_the_five_visible_candidates():
    facts=[{'id':f'skill{i}','label':f'Навык {i}','patterns':[f'Факт {i}']} for i in range(6)]
    scenarios=[basic_scenario(str(i),[fact]) for i,fact in enumerate(facts)]
    result=recommend(STUDENT,fact_failures(facts),set(),list(reversed(scenarios)))
    assert [s['id'] for s in result['suggested_scenarios']]==['0','1','2','3','4']
    assert result['unmatched_criteria']==[{'criterion_id':'fact:skill5','title':'Навык 5'}]


def test_rubric_match_keeps_service_and_level_filters():
    scenarios=[basic_scenario('wrong-service',[ARRIVAL],service='Мослифт'),
        basic_scenario('wrong-level',[ARRIVAL],difficulty='advanced'),basic_scenario('good',[ARRIVAL])]
    result=recommend(STUDENT,fact_failures([ARRIVAL]),set(),scenarios)
    assert [s['id'] for s in result['suggested_scenarios']]==['good']


def test_student_api_match_exposes_only_historical_criterion_identity(env):
    mounted(env)
    historical={**ARRIVAL,'id':'private-arrival','label':'Подтверждение прибытия для повтора','confirmed_by_contact_ids':['duty']}
    session_ids=[store_finished(env,score=50) for _ in range(3)]
    template=next(s for s in env['teacher'].get('/api/scenarios').json() if s['service']=='Мосводоканал')
    with env['app'].state.session_factory() as db:
        original=db.get(Scenario,template['id'])
        data=deepcopy(original.data)
        data.update(title='Проверка следующего упражнения',difficulty='basic',
            required_facts=[{**historical,'patterns':['SECRET_NEXT_ANSWER'],'confirmed_by_contact_ids':['future-duty']}],
            contacts=[{**CONTACT,'id':'future-duty','name':'SECRET_NEXT_CONTACT','reply':'SECRET_NEXT_REPLY','phone':'2999'}],
            reference_response='SECRET_NEXT_REFERENCE',response_limit_seconds=1777)
        for sid in session_ids:
            row=db.get(TrainingSession,sid)
            row.snapshot={**row.snapshot,'required_facts':[deepcopy(historical)],'contacts':[deepcopy(CONTACT)]}
            row.report={'score':50,'requires_review':False,'criteria':[{'id':'fact:private-arrival','title':historical['label'],
                'status':'fail','critical':True,'max_points':35}]}
        db.add(Scenario(id='target-visible',owner_id=original.owner_id,status='approved',is_seed=True,data=data))
        db.add(Scenario(id='target-draft',owner_id=original.owner_id,status='draft',is_seed=True,data=data))
        db.add(Scenario(id='target-unassigned',owner_id=original.owner_id,status='approved',is_seed=False,data=data))
        db.commit()
    response=env['student'].get('/api/recommendations')
    assert response.status_code==200
    payload=response.json();result=payload['items'][0]
    assert payload['policy_version']=='author-v2'
    assert [s['id'] for s in result['suggested_scenarios']]==['target-visible']
    candidate=result['suggested_scenarios'][0]
    assert set(candidate)=={'id','title','service','difficulty','selection_basis','matched_criteria'}
    assert candidate['matched_criteria']==[{'criterion_id':'fact:private-arrival','title':historical['label']}]
    for private in ['SECRET_NEXT_', 'future-duty','2999','1777','required_facts','reference_response','confirmed_by_contact_ids','snapshot','contacts']:
        assert private not in response.text
