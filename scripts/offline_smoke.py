#!/usr/bin/env python3
"""Exercise prepared app in isolated source/temp DB with Python network blocked."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True);args=parser.parse_args()
    blocked=[]
    def denied(*values,**kwargs):
        blocked.append('network_attempt')
        raise RuntimeError('Network is disabled for offline smoke test')
    socket.socket.connect=denied;socket.socket.connect_ex=denied;socket.getaddrinfo=denied
    with tempfile.TemporaryDirectory(prefix='dds-offline-smoke-') as directory:
        isolated=Path(directory);backend=isolated/'backend';backend.mkdir()
        shutil.copytree(ROOT/'backend/app',backend/'app',ignore=shutil.ignore_patterns('__pycache__','*.pyc','.env','.env.*'))
        (backend/'data').mkdir()
        for name in ['classifier.json','knowledge.json','scenarios.json']:
            shutil.copy2(ROOT/'backend/data'/name,backend/'data'/name)
        sys.path.insert(0,str(backend))
        # No .env is copied. All database creation occurs in the temporary source tree.
        os.environ.update(DATABASE_URL=f'sqlite:///{isolated/"smoke.db"}',DEMO_MODE='true',AI_MODE='rules',AI_ENDPOINT='',STATIC_DIR=str(args.bundle.resolve()/'frontend-dist'))
        import uvicorn, httptools, pydantic_core, psycopg
        if sys.platform != 'win32':
            import uvloop
        from fastapi.testclient import TestClient
        from app.main import create_app
        from app.config import Settings
        settings=Settings(_env_file=None,database_url=os.environ['DATABASE_URL'],demo_mode=True,ai_mode='rules',ai_endpoint=None,static_dir=args.bundle.resolve()/'frontend-dist',data_dir=backend/'data')
        app=create_app(settings)
        with TestClient(app) as public,TestClient(app) as teacher,TestClient(app) as student:
            assert public.get('/api/health').json()['database']=='ok'
            index=public.get('/');assert index.status_code==200
            assets=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',index.text)
            assert assets
            for asset in assets:assert public.get(asset).status_code==200,asset
            for client,name in [(teacher,'teacher'),(student,'student')]:assert client.post('/api/auth/login',json={'username':name,'password':'Demo112!'}).status_code==200
            scenarios=teacher.get('/api/scenarios').json()
            scenario=next(s for s in scenarios if s['title']=='Отключение воды в учебном доме')
            uid=student.get('/api/auth/me').json()['id']
            assigned=teacher.post('/api/sessions',json={'scenario_id':scenario['id'],'student_ids':[uid],'mode':'practice'})
            assert assigned.status_code==200;sid=assigned.json()[0]['id']
            assert student.post(f'/api/sessions/{sid}/start',json={}).status_code==200
            sequence=0
            def event(kind,payload=None):
                nonlocal sequence
                sequence+=1
                response=student.post(f'/api/sessions/{sid}/events',json={'client_event_id':f'offline-{sequence}','kind':kind,'payload':payload or {}})
                assert response.status_code==200,response.text
                return response.json()
            event('card_opened');event('status_changed',{'status':'accepted','comment':'Карточка принята.'})
            call=event('call_started',{'phone':'2001'})['reply']['call_id']
            event('trainee_message',{'call_id':call,'text':'Учебная улица, дом 12. Отсутствует холодная вода.'})
            event('call_ended',{'call_id':call});event('status_changed',{'status':'responding','comment':'Бригада направлена.'})
            report=student.post(f'/api/sessions/{sid}/submit',json={}).json()['report']
            assert report['score']==100 and not report['requires_review'],report
            assert teacher.post(f'/api/sessions/{sid}/review',json={'score':100,'comment':'Проверка автономного учебного цикла.'}).status_code==200
            assert student.get('/api/recommendations').json()['items'][0]['sample_size']==1
            assert not blocked,blocked
            result={'result':'passed','python':sys.version.split()[0],'network_attempts':len(blocked),'database':'temporary','dotenv':'not copied','static_assets_checked':len(assets),'scenario_count':len(scenarios),'lifecycle_score':report['score'],'ai_mode':'rules','checks':['health','frontend index/assets','login','assign','start','phone','events','submit','teacher review','recommendations']}
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
