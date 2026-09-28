from app.routes.intake112 import CASES


def test_synthetic_112_intake_and_review(env):
    student, teacher, admin = env['student'], env['teacher'], env['admin']
    catalog = student.get('/api/intake112/cases')
    assert catalog.status_code == 200
    assert len(catalog.json()['cases']) == 2
    assert 'answer' not in str(catalog.json())
    assert admin.get('/api/intake112/cases').status_code == 403

    case = CASES['smoke-entrance']
    card = {**case['answer'], 'services': case['services']}
    card['address'] = card['address'].upper()
    card['caller_phone'] = '89991112233'
    submitted = student.post('/api/intake112/attempts', json={'case_id': 'smoke-entrance', 'card': card})
    assert submitted.status_code == 200, submitted.text
    row = submitted.json()
    assert row['comparison']['matched'] == row['comparison']['total'] == 9
    assert row['review_comment'] is None
    assert teacher.get('/api/intake112/attempts').json()[0]['id'] == row['id']
    assert admin.get('/api/intake112/attempts').status_code == 403
    assert student.post(f"/api/intake112/attempts/{row['id']}/review", json={'comment': 'ok'}).status_code == 403

    reviewed = teacher.post(f"/api/intake112/attempts/{row['id']}/review", json={'comment': 'Адрес и службы выбраны верно.'})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()['review_comment'] == 'Адрес и службы выбраны верно.'
    assert student.get('/api/intake112/attempts').json()[0]['review_comment'] == 'Адрес и службы выбраны верно.'


def test_112_comparison_shows_missed_service_and_wrong_field(env):
    case = CASES['gas-kitchen']
    card = {**case['answer'], 'services': []}
    card['address'] = 'не тот адрес'
    response = env['student'].post('/api/intake112/attempts', json={'case_id': 'gas-kitchen', 'card': card})
    assert response.status_code == 200, response.text
    result = response.json()['comparison']
    assert result['matched'] == 7
    assert next(x for x in result['fields'] if x['key'] == 'address')['matched'] is False
    assert next(x for x in result['services'] if x['name'] == 'Аварийная газовая служба')['matched'] is False
    duplicate = env['student'].post('/api/intake112/attempts', json={'case_id': 'gas-kitchen', 'card': {**card, 'services': ['Полиция', 'Полиция']}})
    assert duplicate.status_code == 422
