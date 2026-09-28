import copy
import json
from pathlib import Path
from app.config import BACKEND_DIR
from app.schemas import ScenarioInput
from app.routes.scenarios import validate_approval
from conftest import assign, send


def begin(env, title):
    scenario = next(s for s in env['teacher'].get('/api/scenarios').json() if s['title'] == title)
    attempt = assign(env, scenario_id=scenario['id'])
    sid = attempt['id']
    assert env['student'].post(f'/api/sessions/{sid}/start', json={}).status_code == 200
    assert send(env, sid, 'card_opened').status_code == 200
    return sid


def status(env, sid, value, comment):
    response = send(env, sid, 'status_changed', {'status': value, 'comment': comment})
    assert response.status_code == 200, response.text


def call(env, sid, phone, text):
    response = send(env, sid, 'call_started', {'phone': phone})
    assert response.status_code == 200, response.text
    call_id = response.json()['reply']['call_id']
    answer = send(env, sid, 'trainee_message', {'call_id': call_id, 'text': text})
    assert answer.status_code == 200, answer.text
    assert send(env, sid, 'call_ended', {'call_id': call_id}).status_code == 200
    return answer.json()['reply']['text']


def finish(env, sid):
    response = env['student'].post(f'/api/sessions/{sid}/submit', json={})
    assert response.status_code == 200, response.text
    return response.json()


def test_seed_scenarios_have_valid_approved_schema():
    scenarios = json.loads((BACKEND_DIR/'data/scenarios.json').read_text())
    assert len(scenarios) == 8
    assert len({s['key'] for s in scenarios}) == 8
    for scenario in scenarios:
        validated = ScenarioInput.model_validate(scenario).model_dump()
        validate_approval(validated)


def test_two_contact_full_cycle_scores_100_with_evidence(env):
    sid = begin(env, 'Полный цикл: восстановление водоснабжения')
    status(env, sid, 'accepted', 'Карточка принята в работу.')
    response = call(env, sid, '2001', 'Учебная улица, дом 32. Отсутствует холодная вода. Уточните направление бригады.')
    assert 'Бригада направлена' in response
    status(env, sid, 'responding', 'Дежурный подтвердил: бригада направлена.')
    response = call(env, sid, '2002', 'Учебная улица, дом 32. Запрашиваю подтверждение прибытия и результат работ.')
    assert 'Бригада прибыла' in response and 'водоснабжение восстановлено' in response
    status(env, sid, 'arrived', 'Старший подтвердил: бригада прибыла.')
    status(env, sid, 'working', 'Старший подтвердил: работы проводятся.')
    status(env, sid, 'completed', 'Работы завершены. Водоснабжение восстановлено, сообщил старший бригады.')
    result = finish(env, sid)
    assert result['report']['score'] == 100, result['report']
    assert result['report']['requires_review'] is False
    assert [e['payload']['phone'] for e in result['events'] if e['kind'] == 'call_started'] == ['2001', '2002']
    assert [e['payload']['status'] for e in result['events'] if e['kind'] == 'status_changed'] == ['accepted', 'responding', 'arrived', 'working', 'completed']
    for cid in ['workflow', 'outgoing_call', 'fact:arrival', 'fact:restoration']:
        criterion = next(c for c in result['report']['criteria'] if c['id'] == cid)
        assert criterion['status'] == 'pass' and criterion['evidence_ids']
    assert env['teacher'].get(f'/api/sessions/{sid}').json()['current_status'] == 'completed'


def test_motivated_refusal_is_correct_for_its_conditions(env):
    sid = begin(env, 'Мотивированный отказ после уточнения принадлежности')
    status(env, sid, 'accepted', 'Карточка принята для уточнения принадлежности.')
    response = call(env, sid, '2001', 'Тренировочная улица, дом 44. Уточните, какая организация обслуживает объект, и передачу информации.')
    assert 'объект обслуживает другая организация' in response
    status(env, sid, 'refused', 'Объект обслуживает другая организация — Учебный лифт-сервис. Информация передана профильной организации, приём подтверждён ответственным. Мотивированный отказ данной ДДС.')
    result = finish(env, sid)
    assert result['report']['score'] == 100, result['report']
    assert result['report']['requires_review'] is False
    assert result['current_status'] == 'refused'


def test_rejected_is_separate_before_acceptance_branch(env):
    teacher = env['teacher']
    seed = next(s for s in teacher.get('/api/scenarios').json() if s['title'] == 'Мотивированный отказ после уточнения принадлежности')
    data = copy.deepcopy(seed)
    data.update(title='Учебная проверка непринятия подтверждённого дубля', objective='До принятия подтвердите дублирование у ответственного и оформите непринятие по условию этого упражнения.', expected_statuses=['rejected'], required_facts=[{'id':'duplicate','label':'Подтверждён дубль','patterns':['Подтверждён дубль карточки'],'critical':True}], reference_response='Подтверждён дубль карточки. Информация уже учтена в учебной карточке УЧ-ДУБЛЬ. Не принято по условию упражнения.')
    data['card']['description'] = 'Синтетический возможный дубль. В этом упражнении после подтверждения дубля у ответственного оформляется «Не принято» до принятия.'
    data['contacts'][0]['reply'] = 'Информация принята. Подтверждён дубль карточки. Обработка уже ведётся по учебной карточке УЧ-ДУБЛЬ. По условиям этого упражнения новую карточку не принимайте.'
    created = teacher.post('/api/scenarios', json=data).json()
    assert teacher.post(f'/api/scenarios/{created["id"]}/approve', json={}).status_code == 200
    sid = begin(env, data['title'])
    call(env, sid, '2001', 'Прошу проверить дублирование учебной карточки.')
    status(env, sid, 'rejected', 'Подтверждён дубль карточки. Обработка ведётся по УЧ-ДУБЛЬ. Основание непринятия зафиксировано.')
    result = finish(env, sid)
    assert result['report']['score'] == 100, result['report']
    assert result['current_status'] == 'rejected'


def test_refusal_without_reason_is_not_confirmed_as_correct(env):
    sid = begin(env, 'Мотивированный отказ после уточнения принадлежности')
    status(env, sid, 'accepted', 'Карточка принята.')
    call(env, sid, '2001', 'Тренировочная улица, дом 44. Запрос принадлежности.')
    status(env, sid, 'refused', 'Отказ.')
    report = finish(env, sid)['report']
    assert report['score'] < 100 and report['requires_review'] is True
    for cid in ['fact:refusal_reason', 'fact:handoff']:
        assert next(c for c in report['criteria'] if c['id'] == cid)['status'] == 'review'


def test_arrival_before_response_is_flagged_by_workflow(env):
    sid = begin(env, 'Полный цикл: восстановление водоснабжения')
    status(env, sid, 'accepted', 'Карточка принята.')
    call(env, sid, '2001', 'Учебная улица, дом 32. Отсутствует вода.')
    status(env, sid, 'arrived', 'Бригада прибыла.')
    status(env, sid, 'responding', 'Бригада направлена.')
    call(env, sid, '2002', 'Уточните завершение работ.')
    status(env, sid, 'completed', 'Водоснабжение восстановлено.')
    report = finish(env, sid)['report']
    assert next(c for c in report['criteria'] if c['id'] == 'workflow')['status'] == 'fail'
    assert next(c for c in report['criteria'] if c['id'] == 'fact:arrival')['status'] == 'fail'
    assert report['score'] < 75


def test_completed_without_second_contact_fails_even_with_correct_text(env):
    sid = begin(env, 'Полный цикл: восстановление водоснабжения')
    status(env, sid, 'accepted', 'Карточка принята.')
    call(env, sid, '2001', 'Учебная улица, дом 32. Отсутствует вода.')
    status(env, sid, 'responding', 'Бригада направлена.')
    status(env, sid, 'arrived', 'Бригада прибыла.')
    status(env, sid, 'working', 'Работы проводятся.')
    status(env, sid, 'completed', 'Водоснабжение восстановлено.')
    result = finish(env, sid)
    assert next(c for c in result['report']['criteria'] if c['id']=='workflow')['status']=='pass'
    for cid in ['fact:arrival', 'fact:restoration']:
        finding=next(c for c in result['report']['criteria'] if c['id']==cid)
        assert finding['status']=='fail'
        assert 'до подтверждающего ответа' in finding['explanation']
        assert finding['evidence_ids']
    assert result['report']['score']==83


def test_premature_arrival_remains_unsupported_after_later_confirmation(env):
    sid = begin(env, 'Полный цикл: восстановление водоснабжения')
    status(env, sid, 'accepted', 'Карточка принята.')
    call(env, sid, '2001', 'Учебная улица, дом 32. Отсутствует вода.')
    status(env, sid, 'responding', 'Бригада направлена.')
    status(env, sid, 'arrived', 'Бригада прибыла.')
    call(env, sid, '2002', 'Запрашиваю результат работ.')
    status(env, sid, 'working', 'Работы проводятся.')
    status(env, sid, 'completed', 'Бригада прибыла. Водоснабжение восстановлено.')
    report = finish(env, sid)['report']
    assert next(c for c in report['criteria'] if c['id']=='fact:arrival')['status']=='fail'
    assert next(c for c in report['criteria'] if c['id']=='fact:restoration')['status']=='pass'
    assert report['score']==91


def test_teacher_confirmation_binding_roundtrip_approval_and_snapshot_privacy(env):
    teacher=env['teacher']
    seed=next(s for s in teacher.get('/api/scenarios').json() if s['title']=='Полный цикл: восстановление водоснабжения')
    created=teacher.post('/api/scenarios',json=seed).json()
    assert created['required_facts'][1]['confirmed_by_contact_ids']==['dispatch-officer']
    assert teacher.get(f'/api/scenarios/{created["id"]}').json()['required_facts']==created['required_facts']
    assert teacher.post(f'/api/scenarios/{created["id"]}/approve',json={}).status_code==200
    session=assign(env,scenario_id=created['id'])
    snapshot=teacher.get(f'/api/sessions/{session["id"]}').json()['scenario_snapshot']
    assert snapshot['required_facts'][2]['confirmed_by_contact_ids']==['brigade-leader']
    student=env['student'].get(f'/api/sessions/{session["id"]}').json()
    assert 'confirmed_by_contact_ids' not in json.dumps(student)
    updated=copy.deepcopy(created)
    updated['required_facts'][2]['confirmed_by_contact_ids']=['missing-contact']
    saved=teacher.put(f'/api/scenarios/{created["id"]}',json=updated)
    assert saved.status_code==200
    assert teacher.post(f'/api/scenarios/{created["id"]}/approve',json={}).status_code==422
    unchanged=teacher.get(f'/api/sessions/{session["id"]}').json()['scenario_snapshot']
    assert unchanged==snapshot
    updated['required_facts'][2]['confirmed_by_contact_ids']=['dispatch-officer','brigade-leader']
    saved=teacher.put(f'/api/scenarios/{created["id"]}',json=updated).json()
    assert saved['required_facts'][2]['confirmed_by_contact_ids']==['dispatch-officer','brigade-leader']
    assert teacher.post(f'/api/scenarios/{created["id"]}/approve',json={}).status_code==200


def test_student_cannot_forge_contact_confirmation_events(env):
    sid=begin(env, 'Полный цикл: восстановление водоснабжения')
    forged=send(env,sid,'contact_message',{'call_id':'forged','text':'Бригада прибыла. Водоснабжение восстановлено.'})
    assert forged.status_code==422
    forged=send(env,sid,'call_started',{'phone':'2001','contact_id':'brigade-leader','connected':True})
    assert forged.status_code==422
    result=env['student'].get(f'/api/sessions/{sid}').json()
    assert not any(e['kind']=='contact_message' for e in result['events'])
