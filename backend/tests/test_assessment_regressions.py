from app.assessment import detect_dispatch, assess


def test_cancellation_is_not_success():
    assert detect_dispatch('Бригада направлена. Выезд бригады отменён.').status != 'pass'


def test_typo_and_abbreviation_preserve_report_meaning():
    assert detect_dispatch('Авар. бригада напр. к месту.').status == 'pass'
    assert detect_dispatch('Бригада напровлена к месту.').status == 'pass'


def test_interrupted_attempt_does_not_assert_unfinished_work_is_failure():
    report = assess({'response_limit_seconds': 30, 'completion_limit_seconds': 180,
                     'expected_statuses': ['accepted', 'responding'], 'required_facts': []}, [],
                    None, '2026-09-19T00:00:00+00:00', stopped=True)
    assert report['requires_review'] is True
    assert report['critical_errors'] == 0
    assert not any(c['status'] == 'fail' for c in report['criteria'])


def test_fact_evidence_points_to_actual_supporting_event():
    snapshot = {'response_limit_seconds': 30, 'completion_limit_seconds': 180, 'expected_statuses': ['accepted'],
                'required_facts': [{'id': 'address', 'label': 'Адрес', 'patterns': ['Учебная улица, дом 7']}]}
    events = [{'id': 'wrong', 'kind': 'status_changed', 'elapsed_seconds': 1, 'payload': {'status': 'accepted', 'comment': 'Принято'}},
              {'id': 'right', 'kind': 'trainee_message', 'elapsed_seconds': 2, 'payload': {'text': 'Учебная улица, дом 7', 'call_id': 'c'}}]
    report = assess(snapshot, events, '2026-09-19T00:00:00+00:00', '2026-09-19T00:00:10+00:00')
    fact = next(c for c in report['criteria'] if c['id'] == 'fact:address')
    assert fact['evidence_ids'] == ['right']
