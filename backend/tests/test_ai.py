import json
from unittest.mock import patch

import pytest
from app.ai import ModelUnavailable, local_url, review_semantics, SemanticReview, ReviewSuggestion
from app.config import Settings
from conftest import start


@pytest.mark.parametrize('endpoint', ['https://remote.example/v1', 'http://example.com/v1', 'http://127.0.0.1@evil.test', 'http://user:secret@localhost:80', 'file:///etc/passwd', None])
def test_model_url_rejects_nonlocal_or_credentials(endpoint):
    with pytest.raises(ModelUnavailable): local_url(endpoint, '/models')


def test_model_url_loopback():
    assert local_url('http://127.0.0.1:11434/v1', '/models') == 'http://127.0.0.1:11434/v1/models'


def test_model_advice_requires_verbatim_evidence_and_valid_criterion():
    answer = SemanticReview(suggestions=[
        ReviewSuggestion(criterion_id='fact:dispatch', observation='Проверить отрицание', quote='Бригада не направлена', needs_review=False),
        ReviewSuggestion(criterion_id='fact:dispatch', observation='Выдуманная цитата', quote='Бригада выехала'),
        ReviewSuggestion(criterion_id='invented', observation='Несуществующий критерий', quote='Бригада не направлена'),
    ])
    snapshot = {'card': {}, 'reference_response': 'Бригада направлена'}
    events = [{'kind': 'status_changed', 'payload': {'comment': 'Бригада не направлена'}}]
    report = {'criteria': [{'id': 'fact:dispatch', 'title': 'Направление', 'status': 'review', 'category': 'content', 'expected': 'Бригада направлена'}], 'score': 50}
    before = json.dumps(report)
    with patch('app.ai.completion', return_value=(answer, 1.2)):
        result = review_semantics(Settings(), snapshot, events, report)
    assert len(result['suggestions']) == 1
    assert result['suggestions'][0]['needs_review'] is True
    assert result['changes_grade'] is False
    assert result['discarded_unsupported'] == 2
    assert json.dumps(report) == before


def test_student_cannot_invoke_teacher_ai_review(env):
    s = start(env)
    assert env['student'].post(f"/api/sessions/{s['id']}/ai-review", json={}).status_code == 403


def test_audio_proxy_auth_and_media_limits(env):
    s = start(env)
    url = f"/api/sessions/{s['id']}/transcribe"
    assert env['public'].post(url, content=b'bad').status_code == 401
    assert env['teacher'].post(url, content=b'bad').status_code == 403
    assert env['student'].post(url, content=b'bad', headers={'Content-Type': 'application/json'}).status_code == 415
    assert env['student'].post(url, content=b'', headers={'Content-Type': 'audio/wav'}).status_code == 422


def test_audio_proxy_returns_reviewable_draft_and_writes_no_event(env):
    s = start(env)
    transcript = {'text': 'Учебный доклад', 'language': 'ru', 'model': 'test-asr', 'duration_seconds': 2, 'latency_seconds': .1}
    import httpx
    async def respond(*args, **kwargs):
        return httpx.Response(200, json=transcript, request=httpx.Request('POST', 'http://localhost/transcribe'))
    before = env['student'].get(f"/api/sessions/{s['id']}").json()
    with patch('app.routes.ai.httpx.AsyncClient.post', side_effect=respond):
        r = env['student'].post(f"/api/sessions/{s['id']}/transcribe", content=b'fake-test-audio', headers={'Content-Type': 'audio/wav'})
    assert r.status_code == 200, r.text
    assert r.json()['requires_human_review'] is True
    after = env['student'].get(f"/api/sessions/{s['id']}").json()
    assert before['events'] == after['events']


def test_ai_offline_status_has_honest_configured_field(env):
    async def failed(*args, **kwargs):
        import httpx
        raise httpx.ConnectError('unavailable')
    with patch('app.routes.ai.httpx.AsyncClient.get', side_effect=failed):
        r = env['teacher'].get('/api/ai/status')
    assert r.status_code == 200
    assert r.json()['language_model']['configured'] is False
    assert r.json()['speech']['available'] is False


def test_voice_proxy_cannot_read_another_session_event(env):
    from conftest import send, assign
    s = start(env)
    call = send(env, s['id'], 'call_started', {'phone': s['contacts'][0]['phone']}).json()
    event = next(e for e in call['session']['events'] if e['kind'] == 'contact_message')
    other = assign(env)
    r = env['student'].get(f"/api/sessions/{other['id']}/events/{event['id']}/audio")
    assert r.status_code == 404


def test_voice_proxy_only_speaks_saved_contact_text(env):
    from conftest import send
    import httpx
    s = start(env)
    call = send(env, s['id'], 'call_started', {'phone': s['contacts'][0]['phone']}).json()
    event = next(e for e in call['session']['events'] if e['kind'] == 'contact_message')
    captured = []
    async def respond(*args, **kwargs):
        captured.append(kwargs['json'])
        return httpx.Response(200, content=b'RIFF-test-WAVE', request=httpx.Request('POST', 'http://localhost/synthesize'))
    with patch('app.routes.ai.httpx.AsyncClient.post', side_effect=respond):
        r = env['student'].get(f"/api/sessions/{s['id']}/events/{event['id']}/audio")
    assert r.status_code == 200
    assert captured == [{'text': event['payload']['text']}]


def test_model_not_called_for_passed_or_formal_criteria():
    report = {'criteria': [
        {'id': 'fact:address', 'status': 'pass', 'category': 'content'},
        {'id': 'timing', 'status': 'review', 'category': 'timing'},
        {'id': 'fact:dispatch', 'status': 'fail', 'category': 'content'},
    ]}
    with patch('app.ai.completion') as model:
        result = review_semantics(Settings(), {}, [], report)
    model.assert_not_called()
    assert result['mode'] == 'not_requested'
    assert result['suggestions'] == []
    assert result['changes_grade'] is False
