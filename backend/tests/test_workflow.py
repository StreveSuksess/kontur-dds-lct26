import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.models import Scenario, TrainingSession, User, Event
from conftest import assign,send,start


def test_full_lifecycle_and_score_review_history(env):
    s=start(env);sid=s['id'];student=env['student'];teacher=env['teacher']
    assert send(env,sid,'card_opened').status_code==200
    assert send(env,sid,'status_changed',{'status':'accepted','comment':'Карточка принята.'}).status_code==200
    call=send(env,sid,'call_started',{'phone':s['contacts'][0]['phone']}).json()
    call_id=call['reply']['call_id']
    assert call['event']['payload']['connected'] is True
    assert 'Готов принять' in call['reply']['text']
    report=f"Адрес: {s['card']['address']}. {s['card']['description']}"
    answer=send(env,sid,'trainee_message',{'text':report,'call_id':call_id}).json()
    assert 'Информация принята' in answer['reply']['text']
    assert send(env,sid,'call_ended',{'call_id':call_id}).status_code==200
    send(env,sid,'status_changed',{'status':'responding','comment':'Дежурная бригада направлена к месту.'})
    submitted=student.post(f'/api/sessions/{sid}/submit',json={}).json()
    assert submitted['status']=='submitted'
    assert submitted['report']['score']==100,submitted['report']
    assert submitted['report']['critical_errors']==0
    report_before=copy.deepcopy(submitted['report'])
    first=teacher.post(f'/api/sessions/{sid}/review',json={'score':93,'comment':'Преподаватель уточнил оценку полноты доклада.'}).json()
    assert first['report']['score']==100
    assert first['report']['teacher_review']['score']==93
    second=teacher.post(f'/api/sessions/{sid}/review',json={'score':96,'comment':'После дополнительного разбора формулировка признана допустимой.'}).json()
    assert second['report']['criteria']==report_before['criteria']
    review_events=[e for e in second['events'] if e['kind']=='review_saved']
    assert review_events[-1]['payload']['previous_review']['score']==93
    assert second['report']['teacher_review']['score']==96
    analytics=teacher.get('/api/analytics').json()
    assert analytics['average_score']==96
    assert student.post(f'/api/sessions/{sid}/events',json={'kind':'card_opened','client_event_id':'late','payload':{}}).status_code==409
    repeat=student.post(f'/api/sessions/{sid}/repeat',json={}).json()
    assert repeat['id']!=sid and repeat['events']==[] and repeat['report'] is None
    csv=student.get(f'/api/sessions/{sid}/export.csv')
    assert csv.status_code==200 and csv.content.startswith(b'\xef\xbb\xbf')


def test_authorization_and_private_reference(env):
    assert env['public'].get('/api/auth/me').status_code==401
    assert env['student'].get('/api/scenarios').status_code==403
    assert env['admin'].get('/api/sessions').status_code==403
    assert env['admin'].post('/api/sessions',json={}).status_code==403
    assert env['student'].get('/api/admin/audit').status_code==403
    s=assign(env);sid=s['id']
    public=env['student'].get(f'/api/sessions/{sid}').json()
    for key in ['scenario_snapshot','snapshot','reference_response','required_facts','expected_statuses']:
        assert key not in public
    assert all(set(c)=={'id','name','role','phone'} for c in public['contacts'])
    assert 'reply' not in json.dumps(public,ensure_ascii=False)
    assert public['report'] is None
    assert 'scenario_snapshot' in env['teacher'].get(f'/api/sessions/{sid}').json()


def test_foreign_student_and_teacher_isolation(env):
    s=assign(env);sid=s['id']
    for username,role in [('other_student','student'),('other_teacher','teacher')]:
        created=env['admin'].post('/api/admin/users',json={'username':username,'name':'Другой пользователь','password':'OtherPass112!','role':role}).json()
        other=TestClient(env['app']);assert other.post('/api/auth/login',json={'username':username,'password':'OtherPass112!'}).status_code==200
        assert other.get(f'/api/sessions/{sid}').status_code==403
        assert other.get('/api/sessions').json()==[]
        assert other.get('/api/analytics').json()['total_sessions']==0
        assert other.post(f'/api/sessions/{sid}/review',json={'score':100,'comment':'Чужая оценка'}).status_code==403
        other.close()


def test_approve_gate_and_immutable_snapshot(env):
    t=env['teacher'];seed=t.get('/api/scenarios').json()[0]
    assert t.put(f'/api/scenarios/{seed["id"]}',json=seed).status_code==403
    draft=t.post(f'/api/scenarios/{seed["id"]}/duplicate',json={}).json()
    response=t.post('/api/sessions',json={'scenario_id':draft['id'],'student_ids':[env['student'].get('/api/auth/me').json()['id']],'mode':'practice'})
    assert response.status_code==409
    approved=t.post(f'/api/scenarios/{draft["id"]}/approve',json={}).json()
    s=assign(env,scenario_id=approved['id'])
    changed=copy.deepcopy(approved);changed['card']['address']='Другой учебный адрес, 999';changed['reference_response']='Новый эталон'
    updated=t.put(f'/api/scenarios/{approved["id"]}',json=changed).json()
    assert updated['version']==approved['version']+1 and updated['status']=='draft'
    old=t.get(f'/api/sessions/{s["id"]}').json()
    assert old['card']['address']==approved['card']['address']
    assert old['scenario_snapshot']['reference_response']==approved['reference_response']


def test_approval_requires_complete_criteria(env):
    t=env['teacher'];seed=t.get('/api/scenarios').json()[0]
    seed['required_facts']=[]
    row=t.post('/api/scenarios',json=seed).json()
    assert row['status']=='draft'
    assert t.post(f'/api/scenarios/{row["id"]}/approve',json={}).status_code==422


def test_event_idempotency_under_parallel_retries(env):
    s=start(env);sid=s['id'];phone=s['contacts'][0]['phone']
    def retry(_):return send(env,sid,'call_started',{'phone':phone},event_id='same-call')
    with ThreadPoolExecutor(max_workers=6) as pool:responses=list(pool.map(retry,range(6)))
    assert all(r.status_code==200 for r in responses),[r.text for r in responses]
    assert all(r.json()==responses[0].json() for r in responses)
    stored=env['student'].get(f'/api/sessions/{sid}').json()
    assert len([e for e in stored['events'] if e['kind']=='call_started'])==1
    assert len([e for e in stored['events'] if e['kind']=='contact_message'])==1
    assert send(env,sid,'call_started',{'phone':'9999'},event_id='same-call').status_code==409
    env['student'].post(f'/api/sessions/{sid}/submit',json={})
    assert retry(0).json()==responses[0].json()


def test_submit_is_idempotent(env):
    s=start(env);sid=s['id'];a=env['student'].post(f'/api/sessions/{sid}/submit',json={}).json();b=env['student'].post(f'/api/sessions/{sid}/submit',json={}).json()
    assert a==b
    assert len([e for e in b['events'] if e['kind']=='session_submitted'])==1


def test_invalid_phone_and_call_state_are_not_success(env):
    s=start(env);sid=s['id']
    bad=send(env,sid,'call_started',{'phone':'89123456789'}).json()
    assert bad['event']['payload']['connected'] is False
    assert send(env,sid,'trainee_message',{'text':'Доклад','call_id':bad['reply']['call_id']}).status_code==409
    good=send(env,sid,'call_started',{'phone':s['contacts'][0]['phone']}).json()
    cid=good['reply']['call_id']
    assert send(env,sid,'call_started',{'phone':s['contacts'][0]['phone']}).status_code==409
    assert send(env,sid,'trainee_message',{'text':'Доклад','call_id':'invented'}).status_code==409
    assert send(env,sid,'call_ended',{'call_id':cid}).status_code==200
    assert send(env,sid,'trainee_message',{'text':'Поздний доклад','call_id':cid}).status_code==409


def test_payload_limits_and_exam_hints(env):
    s=start(env,mode='exam');sid=s['id']
    assert send(env,sid,'hint_used',{'hint':'Тест'}).status_code==403
    assert send(env,sid,'status_changed',{'status':'accepted','comment':'x'*2000}).status_code==422
    assert send(env,sid,'status_changed',{'status':'accepted','comment':'  '}).status_code==422
    assert send(env,sid,'status_changed',{'status':'invented'}).status_code==422
    assert send(env,sid,'call_started',{'phone':'2001','connected':True}).status_code==422
    assert env['student'].put(f'/api/sessions/{sid}/draft',json={'draft':{'reference_response':'hack'}}).status_code==422
    assert env['student'].put(f'/api/sessions/{sid}/draft',json={'draft':{'comment':'Сохранённый черновик'}}).status_code==200
    assert env['student'].get(f'/api/sessions/{sid}').json()['draft']['comment']=='Сохранённый черновик'
    env['student'].post(f'/api/sessions/{sid}/submit',json={})
    assert env['student'].post(f'/api/sessions/{sid}/repeat',json={}).status_code==403
    assert env['teacher'].post(f'/api/sessions/{sid}/repeat',json={}).status_code==200


def test_deactivated_cookie_and_admin_no_self_lock(env):
    admin=env['admin'];sid=env['student'].get('/api/auth/me').json()['id'];aid=admin.get('/api/auth/me').json()['id']
    assert admin.patch(f'/api/admin/users/{aid}',json={'active':False}).status_code==409
    assert admin.patch(f'/api/admin/users/{sid}',json={'active':False}).status_code==200
    assert env['student'].get('/api/auth/me').status_code==401
    assert admin.patch(f'/api/admin/users/{sid}',json={'active':True}).status_code==200
    assert env['student'].get('/api/auth/me').status_code==401


def test_csrf_cookie_flags_and_logout(env):
    student=env['student']
    response=student.post('/api/auth/login',json={'username':'student','password':'Demo112!'})
    cookie=response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=strict' in cookie
    assert student.post('/api/auth/logout',json={},headers={'Origin':'https://malicious.example'}).status_code==403
    assert student.get('/api/auth/me').status_code==200
    assert student.post('/api/auth/logout',json={}).status_code==200
    assert student.get('/api/auth/me').status_code==401


def test_stopping_and_review_reason(env):
    s=assign(env);sid=s['id']
    assert env['teacher'].post(f'/api/sessions/{sid}/review',json={'score':50,'comment':'До работы'}).status_code==409
    stopped=env['teacher'].post(f'/api/sessions/{sid}/stop',json={}).json()
    assert stopped['status']=='stopped' and stopped['report']['requires_review']
    assert 'остановлена' in stopped['report']['summary']
    assert env['teacher'].post(f'/api/sessions/{sid}/review',json={'score':50,'comment':'   '}).status_code==422
    assert env['student'].post(f'/api/sessions/{sid}/start',json={}).status_code==409


def test_classifier_provenance_and_honest_generator(env):
    result=env['student'].get('/api/classifier?q=14100100').json()
    assert result['total']==1 and result['items'][0]['source_row']
    detail=env['student'].get('/api/classifier/14100100').json()
    assert isinstance(detail['routing'],dict)
    r=env['teacher'].post('/api/scenarios/generate',json={'incident_code':'14100100','service':'Мослифт','difficulty':'basic','instructions':'Синтетический случай'})
    assert r.status_code==200,r.text
    draft=r.json();assert draft['status']=='draft' and 'templates' in draft['source_note']


def test_profile_assignment_mismatch(env):
    students=env['teacher'].get('/api/users').json()
    lift=next(x for x in students if x['username']=='student_lift')
    water=next(s for s in env['teacher'].get('/api/scenarios').json() if s['service']=='Мосводоканал')
    r=env['teacher'].post('/api/sessions',json={'scenario_id':water['id'],'student_ids':[lift['id']],'mode':'practice'})
    assert r.status_code==422


def test_backup_restore_readability_and_admin_audit_privacy(env):
    s=start(env)
    send(env,s['id'],'status_changed',{'status':'accepted','comment':'НЕПУБЛИЧНЫЙ УЧЕБНЫЙ ТЕКСТ'})
    response=env['admin'].post('/api/admin/backup',json={})
    assert response.status_code==200,response.text
    info=response.json();path=env['app'].state.settings.backup_dir/info['filename']
    assert path.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(path) as restored:
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert restored.execute('SELECT count(*) FROM training_sessions').fetchone()[0]==1
    feed=env['admin'].get('/api/admin/audit').text
    assert 'НЕПУБЛИЧНЫЙ' not in feed and 'Demo112!' not in feed
    assert 'backup_created' in feed


def test_csv_formula_injection_escaped(env):
    s=start(env);sid=s['id']
    env['student'].post(f'/api/sessions/{sid}/submit',json={})
    env['teacher'].post(f'/api/sessions/{sid}/review',json={'score':42,'comment':'=HYPERLINK("bad")'})
    text=env['student'].get(f'/api/sessions/{sid}/export.csv').text
    assert "'=HYPERLINK" in text


def test_client_cannot_replace_server_rubric_or_clock(env):
    s=start(env);sid=s['id']
    forged={'status':'responding','comment':'Бригада направлена.','expected_statuses':['responding'],'elapsed_seconds':1,'reference_response':'Всё зачтено'}
    assert send(env,sid,'status_changed',forged).status_code==422
    assert env['student'].put(f'/api/sessions/{sid}/draft',json={'draft':{'score':100}}).status_code==422
    actual=env['student'].get(f'/api/sessions/{sid}').json()
    assert actual['current_status'] is None
    assert actual['report'] is None
    assert all(e['kind']!='status_changed' for e in actual['events'])


def test_foreign_teacher_cannot_read_or_edit_owned_scenario(env):
    t=env['teacher'];seed=t.get('/api/scenarios').json()[0]
    own=t.post(f'/api/scenarios/{seed["id"]}/duplicate',json={}).json()
    env['admin'].post('/api/admin/users',json={'username':'teacher_b','name':'Второй преподаватель','password':'TeacherB112!','role':'teacher'})
    other=TestClient(env['app']);other.post('/api/auth/login',json={'username':'teacher_b','password':'TeacherB112!'})
    try:
        assert other.get(f'/api/scenarios/{own["id"]}').status_code==403
        assert other.put(f'/api/scenarios/{own["id"]}',json=own).status_code==403
        assert other.post(f'/api/scenarios/{own["id"]}/approve',json={}).status_code==403
        assert own['id'] not in {s['id'] for s in other.get('/api/scenarios').json()}
    finally:other.close()


def test_fresh_production_database_has_no_known_demo_accounts(tmp_path):
    from app.config import Settings,BACKEND_DIR
    from app.main import create_app
    app=create_app(Settings(database_url=f'sqlite:///{tmp_path}/production.db',demo_mode=False,bootstrap_admin_password='UniqueBootstrap112!',data_dir=BACKEND_DIR/'data'))
    with TestClient(app) as client:
        for name in ['teacher','student','admin']:
            assert client.post('/api/auth/login',json={'username':name,'password':'Demo112!'}).status_code==401
        response=client.post('/api/auth/login',json={'username':'admin','password':'UniqueBootstrap112!'})
        assert response.status_code==200
        users=client.get('/api/users').json()
        assert len(users)==1 and users[0]['role']=='admin'


def test_same_event_id_is_scoped_to_attempt(env):
    first=start(env);second=start(env)
    assert send(env,first['id'],'card_opened',event_id='local-id-1').status_code==200
    assert send(env,second['id'],'card_opened',event_id='local-id-1').status_code==200
    assert env['student'].get(f'/api/sessions/{first["id"]}').json()['id']!=env['student'].get(f'/api/sessions/{second["id"]}').json()['id']


def test_compact_replay_freezes_draft_status_and_event_prefix(env):
    from sqlalchemy import inspect
    s=start(env);sid=s['id'];student=env['student']
    student.put(f'/api/sessions/{sid}/draft',json={'draft':{'comment':'Первый черновик'}})
    original=send(env,sid,'call_started',{'phone':s['contacts'][0]['phone']},event_id='frozen').json()
    cid=original['reply']['call_id']
    student.put(f'/api/sessions/{sid}/draft',json={'draft':{'comment':'Изменённый черновик'}})
    send(env,sid,'trainee_message',{'call_id':cid,'text':'Новый доклад, которого не было при первом ответе'})
    send(env,sid,'status_changed',{'status':'accepted','comment':'Новый статус'})
    student.post(f'/api/sessions/{sid}/submit',json={})
    env['teacher'].post(f'/api/sessions/{sid}/review',json={'score':33,'comment':'Поздняя экспертная оценка'})
    replay=send(env,sid,'call_started',{'phone':s['contacts'][0]['phone']},event_id='frozen').json()
    assert replay==original
    assert replay['session']['draft']['comment']=='Первый черновик'
    assert replay['session']['status']=='active' and replay['session']['report'] is None
    with env['app'].state.session_factory() as db:
        stored=db.scalar(select(Event).where(Event.session_id==sid,Event.client_event_id=='frozen'))
        assert 'response_cache' in inspect(stored).unloaded
        cache=stored.response_cache
        assert cache['_cache_version']==2
        assert 'events' not in cache['session_state']
        assert set(cache)=={'_cache_version','event','reply','session_state','event_prefix_sequence'}
        assert cache['event_prefix_sequence']==len(original['session']['events'])


def test_replay_reads_legacy_full_response_cache(env):
    s=start(env);sid=s['id']
    original=send(env,sid,'card_opened',event_id='legacy').json()
    with env['app'].state.session_factory() as db:
        stored=db.scalar(select(Event).where(Event.session_id==sid,Event.client_event_id=='legacy'))
        stored.response_cache=copy.deepcopy(original);db.commit()
    assert send(env,sid,'card_opened',event_id='legacy').json()==original
