from conftest import assign, send
from datetime import datetime, timedelta, timezone
from app.models import TrainingSession


def test_teacher_delivers_multiple_cards_with_one_server_start(env):
    first = assign(env)
    second = assign(env)
    ids = [first['id'], second['id']]

    delivered = env['teacher'].post('/api/sessions/arrive', json={'session_ids': ids})
    assert delivered.status_code == 200, delivered.text
    cards = delivered.json()
    assert [card['id'] for card in cards] == ids
    assert all(card['status'] == 'active' for card in cards)
    assert cards[0]['started_at'] == cards[1]['started_at']
    assert all(card['events'][0]['kind'] == 'session_started' for card in cards)

    # Opening one card later must not restart either clock.
    assert send(env, ids[0], 'card_opened').status_code == 200
    queued = env['student'].get(f'/api/sessions/{ids[1]}').json()
    assert queued['started_at'] == cards[0]['started_at']
    assert not any(event['kind'] == 'card_opened' for event in queued['events'])
    reopened = env['student'].post(f'/api/sessions/{ids[1]}/start', json={}).json()
    assert reopened['started_at'] == cards[0]['started_at']

    # A card left in the queue is timed from delivery, not from opening it.
    with env['app'].state.session_factory() as db:
        row = db.get(TrainingSession, ids[1])
        row.started_at = (datetime.now(timezone.utc) - timedelta(seconds=65)).isoformat()
        db.commit()
    opened = send(env, ids[1], 'card_opened').json()
    assert opened['event']['elapsed_seconds'] >= 60
    report = env['student'].post(f'/api/sessions/{ids[1]}/submit', json={}).json()['report']
    assert next(c for c in report['criteria'] if c['id'] == 'reaction')['status'] == 'fail'


def test_arrival_batch_validates_every_card_before_activation(env):
    pending = assign(env)
    active = assign(env)
    assert env['teacher'].post('/api/sessions/arrive', json={'session_ids': [active['id']]}).status_code == 200
    failed = env['teacher'].post('/api/sessions/arrive', json={'session_ids': [pending['id'], active['id']]})
    assert failed.status_code == 409
    assert env['student'].get(f'/api/sessions/{pending["id"]}').json()['status'] == 'assigned'
    assert env['student'].post('/api/sessions/arrive', json={'session_ids': [pending['id']]}).status_code == 403
    assert env['teacher'].post('/api/sessions/arrive', json={'session_ids': [pending['id'], pending['id']]}).status_code == 422
