from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings, BACKEND_DIR


@pytest.fixture
def env(tmp_path):
    settings=Settings(database_url=f'sqlite:///{tmp_path}/test.db',demo_mode=True,backup_dir=tmp_path/'backups',data_dir=BACKEND_DIR/'data',static_dir=tmp_path/'no-static')
    app=create_app(settings)
    with TestClient(app) as client:
        clients={name:TestClient(app) for name in ['teacher','student','admin']}
        for name,c in clients.items():
            r=c.post('/api/auth/login',json={'username':name,'password':'Demo112!'})
            assert r.status_code==200,r.text
        yield {'app':app,'public':client,**clients}
        for c in clients.values():c.close()


def assign(env,mode='practice',scenario_id=None,student_id=None):
    t=env['teacher']
    scenario_id=scenario_id or t.get('/api/scenarios').json()[0]['id']
    student_id=student_id or env['student'].get('/api/auth/me').json()['id']
    r=t.post('/api/sessions',json={'scenario_id':scenario_id,'student_ids':[student_id],'mode':mode})
    assert r.status_code==200,r.text
    return r.json()[0]


def send(env,sid,kind,payload=None,event_id=None):
    from uuid import uuid4
    return env['student'].post(f'/api/sessions/{sid}/events',json={'client_event_id':event_id or str(uuid4()),'kind':kind,'payload':payload or {}})


def start(env,mode='practice'):
    s=assign(env,mode)
    r=env['student'].post(f'/api/sessions/{s["id"]}/start',json={})
    assert r.status_code==200,r.text
    return r.json()
