#!/usr/bin/env python3
"""Isolated real-HTTP smoke load. Never connects to the working demo database.

backend/.venv/bin/python scripts/load_test.py --output docs/load-test-results.json
This measures API traffic, not browser rendering, long-run capacity or target hardware.
"""
import argparse
import asyncio
import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.auth import password_hash
from app.db import create_database
from app.models import User, AuthSession


def summary(samples, elapsed):
    values = sorted(t for t, _ in samples)
    def percentile(p):
        return round(values[min(len(values)-1, int((len(values)-1)*p))]*1000, 2) if values else None
    return {'requests': len(samples), 'errors': sum(s < 200 or s >= 300 for _, s in samples),
            'duration_seconds': round(elapsed, 3), 'requests_per_second': round(len(samples)/elapsed, 2),
            'p50_ms': percentile(.5), 'p95_ms': percentile(.95), 'p99_ms': percentile(.99),
            'status_codes': {str(s): sum(v == s for _, v in samples) for s in sorted({s for _, s in samples})}}


async def run(base, db_url):
    engine, factory = create_database(db_url)
    tokens, ids = [], []
    # Fixture creation is deliberately outside the measurement. Each user and
    # cookie is distinct; login hashing is not part of a lessons API load test.
    hashed = password_hash(secrets.token_urlsafe(32))
    with factory() as db:
        for i in range(100):
            user = User(username=f'load_{i:03}', name=f'Нагрузочный АРМ {i:03}', role='student',
                        password_hash=hashed, service='Учебная ДДС', group_name='Изолированный тест')
            db.add(user); db.flush(); ids.append(user.id)
            token = secrets.token_urlsafe(40); tokens.append(token)
            db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), user_id=user.id,
                               expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()))
        db.commit()
    engine.dispose()
    async with httpx.AsyncClient(base_url=base, timeout=60) as teacher:
        response = await teacher.post('/api/auth/login', json={'username': 'teacher', 'password': 'Demo112!'})
        response.raise_for_status()
        scenarios = (await teacher.get('/api/scenarios')).json()
        response = await teacher.post('/api/sessions', json={'scenario_id': scenarios[0]['id'], 'student_ids': ids[:20], 'mode': 'practice'})
        response.raise_for_status()
        session_ids = [s['id'] for s in response.json()]
    clients = [httpx.AsyncClient(base_url=base, timeout=60, cookies={'dds_session': t}) for t in tokens]
    async def measure(client, method, path, **kwargs):
        start = time.perf_counter()
        try:
            r = await client.request(method, path, **kwargs)
            return time.perf_counter()-start, r.status_code
        except httpx.HTTPError:
            return time.perf_counter()-start, 0
    try:
        for i in range(20):
            (await clients[i].post(f'/api/sessions/{session_ids[i]}/start', json={})).raise_for_status()
        start = time.perf_counter()
        samples = await asyncio.gather(*[
            measure(client, 'GET', path)
            for client in clients for path in ['/api/auth/me', '/api/sessions', '/api/classifier?q=вод&limit=10']
        ])
        reads = summary(samples, time.perf_counter()-start)
        async def writer(i):
            out = []
            for n in range(10):
                out.append(await measure(clients[i], 'POST', f'/api/sessions/{session_ids[i]}/events',
                                         json={'client_event_id': f'load-{i}-{n}', 'kind': 'status_changed',
                                               'payload': {'status': 'accepted', 'comment': 'Учебная запись нагрузочного теста'}}))
            return out
        start = time.perf_counter()
        batches = await asyncio.gather(*(writer(i) for i in range(20)))
        writes = summary([s for batch in batches for s in batch], time.perf_counter()-start)
        start = time.perf_counter()
        samples = await asyncio.gather(*[measure(clients[i], 'POST', f'/api/sessions/{session_ids[i]}/submit', json={}) for i in range(20)])
        reports = summary(samples, time.perf_counter()-start)
        # Persistence is checked after completed HTTP writes, not inferred from 200s.
        engine, factory = create_database(db_url)
        from sqlalchemy import select, func
        from app.models import Event, TrainingSession
        with factory() as db:
            stored = db.scalar(select(func.count()).select_from(Event).where(Event.kind == 'status_changed'))
            completed = db.scalar(select(func.count()).select_from(TrainingSession).where(TrainingSession.status == 'submitted'))
        engine.dispose()
        return {'read_100_users': reads, 'write_20_sessions': writes, 'report_20_sessions': reports,
                'persistence': {'expected_status_events': 200, 'stored_status_events': stored,
                                'expected_completed_sessions': 20, 'stored_completed_sessions': completed},
                'targets': {'api_p95_under_2_seconds': reads['p95_ms'] < 2000 and reads['errors'] == 0,
                            'event_requests_at_least_100_per_second': writes['requests_per_second'] >= 100 and writes['errors'] == 0,
                            'reports_p95_under_30_seconds': reports['p95_ms'] < 30000 and reports['errors'] == 0}}
    finally:
        await asyncio.gather(*(c.aclose() for c in clients))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/load-test-results.json')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='dds-load-') as directory:
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
        db_url = f'sqlite:///{directory}/load.sqlite3'
        env = {**os.environ, 'DATABASE_URL': db_url, 'DEMO_MODE': 'true', 'AI_MODE': 'rules'}
        with open(Path(directory) / 'server.log', 'w+') as log:
            proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--log-level', 'warning'],
                                    cwd=ROOT/'backend', env=env, stdout=log, stderr=log)
            try:
                base = f'http://127.0.0.1:{port}'
                for _ in range(900):
                    if proc.poll() is not None:
                        log.seek(0); raise RuntimeError(log.read())
                    try:
                        if httpx.get(base+'/api/health', timeout=1).is_success: break
                    except httpx.HTTPError: pass
                    time.sleep(.1)
                else:
                    log.seek(0)
                    raise RuntimeError('Test server did not start within 90s: '+log.read()[-4000:])
                result = asyncio.run(run(base, db_url))
                result.update({'generated_at': datetime.now(timezone.utc).isoformat(),
                               'platform': platform.platform(), 'python': platform.python_version(),
                               'database': 'SQLite WAL, isolated temporary database', 'server_workers': 1,
                               'limitations': ['API-only: no browser rendering measurement.',
                                               'Local host differs from target classroom hardware and network.',
                                               'Short burst: 300 reads, 200 writes and 20 reports; not a soak test.',
                                               'One event request writes several SQL rows; throughput is HTTP commits, not a raw SQL INSERT benchmark.',
                                               'User fixture creation and password hashing excluded; 100 distinct authenticated users.']})
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
                print(json.dumps(result, ensure_ascii=False, indent=2))
            finally:
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()


if __name__ == '__main__':
    main()
