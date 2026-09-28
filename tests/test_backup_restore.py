"""Run with python3 -m unittest discover -s tests -p test_backup_restore.py -v.

The SQLite safety tests use stdlib only. The final end-to-end test runs in the
project's backend .venv (and reports a skip explicitly if it is not installed).
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import closing, contextmanager

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import backup
import restore

DDL='''
CREATE TABLE users(id TEXT PRIMARY KEY,username TEXT,name TEXT,password_hash TEXT,role TEXT,service TEXT,group_name TEXT,active BOOLEAN);
CREATE UNIQUE INDEX unique_username ON users(username);
CREATE TABLE auth_sessions(token_hash TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires_at TEXT);
CREATE TABLE scenarios(id TEXT PRIMARY KEY,owner_id TEXT REFERENCES users(id),is_seed BOOLEAN,status TEXT,version INTEGER,data JSON,created_at TEXT,updated_at TEXT);
CREATE TABLE training_sessions(id TEXT PRIMARY KEY,scenario_id TEXT REFERENCES scenarios(id),student_id TEXT REFERENCES users(id),teacher_id TEXT REFERENCES users(id),mode TEXT,status TEXT,snapshot JSON,assigned_at TEXT,started_at TEXT,finished_at TEXT,current_status TEXT,draft JSON,report JSON);
CREATE TABLE events(id TEXT PRIMARY KEY,session_id TEXT REFERENCES training_sessions(id),client_event_id TEXT,kind TEXT,at TEXT,elapsed_seconds REAL,payload JSON,sequence INTEGER,request_hash TEXT,response_cache JSON,UNIQUE(session_id,client_event_id));
CREATE TABLE audit(id TEXT PRIMARY KEY,actor_id TEXT REFERENCES users(id),action TEXT,entity_type TEXT,entity_id TEXT,at TEXT,details JSON);
CREATE TABLE intake112_attempts(id TEXT PRIMARY KEY,case_id TEXT,student_id TEXT REFERENCES users(id),group_name TEXT,created_at TEXT,submitted_at TEXT,card JSON,comparison JSON,review_comment TEXT,reviewed_at TEXT,reviewed_by TEXT REFERENCES users(id));
'''


@contextmanager
def database(path):
    with closing(sqlite3.connect(path)) as conn:
        with conn:
            yield conn


def make_database(path):
    with database(path) as conn:
        conn.executescript(DDL)
        conn.execute("INSERT INTO users VALUES ('user','student','Учебный участник','synthetic-hash','student','ДДС','Группа',1)")
        conn.execute("INSERT INTO auth_sessions VALUES ('old-token-hash','user','2099-01-01')")
        conn.execute("INSERT INTO scenarios VALUES ('scenario','user',0,'approved',1,?, '2026-09-19','2026-09-19')",(json.dumps({'title':'Сохранённый учебный случай'},ensure_ascii=False),))
        conn.execute("INSERT INTO training_sessions VALUES ('attempt','scenario','user','user','practice','reviewed',?,'2026-09-19','2026-09-19','2026-09-19','responding',?,?)",(json.dumps({'title':'Сохранённый учебный случай'},ensure_ascii=False),json.dumps({'comment':'Непотерянный черновик'},ensure_ascii=False),json.dumps({'score':70,'teacher_review':{'score':90,'comment':'Причина экспертной коррекции'}},ensure_ascii=False)))
        conn.execute("INSERT INTO events VALUES ('event','attempt','client-1','status_changed','2026-09-19',12,?,1,'request-hash',NULL)",(json.dumps({'comment':'Бригада направлена на учебный адрес'},ensure_ascii=False),))
        conn.execute("INSERT INTO audit VALUES ('audit','user','review_saved','session','attempt','2026-09-19','{}')")
        conn.execute("INSERT INTO intake112_attempts VALUES ('intake','synthetic-case','user','Группа','2026-09-19','2026-09-19',?,?,?,'2026-09-19','user')",(json.dumps({'address':'Учебная улица, дом 10'},ensure_ascii=False),json.dumps({'matched':1,'total':1}), 'Проверенный учебный разбор'))


class BackupRestoreTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.source=self.root/'source.sqlite3'
        make_database(self.source)
    def tearDown(self):self.directory.cleanup()

    def test_complete_roundtrip_counts_texts_and_cleared_tokens(self):
        original_hash=hashlib.sha256(self.source.read_bytes()).hexdigest()
        archived=self.root/'backup.sqlite3';restored=self.root/'restored.sqlite3'
        b=backup.backup_database(self.source,archived)
        r=restore.restore_database(archived,restored)
        self.assertEqual(b['counts_before'],b['counts_after'])
        self.assertEqual(r['auth_sessions_removed'],1)
        for table,count in b['counts_after'].items():
            self.assertEqual(r['counts_after'][table],0 if table=='auth_sessions' else count)
        self.assertEqual(original_hash,hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(hashlib.sha256(restored.read_bytes()).hexdigest(),r['sha256'])
        with database(restored) as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
            self.assertIn('Бригада направлена',conn.execute('SELECT payload FROM events').fetchone()[0])
            self.assertIn('Причина экспертной коррекции',conn.execute('SELECT report FROM training_sessions').fetchone()[0])
            self.assertIn('Проверенный учебный разбор',conn.execute('SELECT review_comment FROM intake112_attempts').fetchone()[0])
            self.assertEqual(conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0],0)
        with database(archived) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0],1)
        self.assertEqual(restored.stat().st_mode & 0o777,0o600)
        self.assertFalse(list(self.root.glob('.*.tmp*')))

    def test_refuses_existing_destination_without_overwrite(self):
        destination=self.root/'existing.sqlite3';destination.write_bytes(b'keep this file')
        for operation in [backup.backup_database,restore.restore_database]:
            with self.assertRaises(backup.BackupError):operation(self.source,destination)
            self.assertEqual(destination.read_bytes(),b'keep this file')
        with self.assertRaises(backup.BackupError):restore.restore_database(self.source,self.source)

    def test_concurrent_destination_is_not_clobbered(self):
        target=self.root/'raced.sqlite3';publish=backup.publish_new_file
        def race(temp,destination):
            destination.write_bytes(b'created by another process')
            return publish(temp,destination)
        with patch.object(backup,'publish_new_file',race):
            with self.assertRaises(backup.BackupError):restore.restore_database(self.source,target)
        self.assertEqual(target.read_bytes(),b'created by another process')
        self.assertFalse(list(self.root.glob('.*.tmp*')))

    def test_rejects_wrong_schema_and_untrusted_trigger(self):
        for sql,name in [("DROP TABLE audit",'missing'),("CREATE TRIGGER dangerous AFTER DELETE ON auth_sessions BEGIN DELETE FROM events; END",'trigger')]:
            source=self.root/(name+'.sqlite3');make_database(source)
            with database(source) as conn:conn.execute(sql)
            with self.assertRaises(backup.BackupError):restore.restore_database(source,self.root/(name+'-output.sqlite3'))
            self.assertFalse((self.root/(name+'-output.sqlite3')).exists())
        with database(self.root/'trigger.sqlite3') as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM events').fetchone()[0],1)

    def test_rejects_foreign_key_corruption_before_clearing_tokens(self):
        with database(self.source) as conn:conn.execute("UPDATE auth_sessions SET user_id='missing-user'")
        with self.assertRaises(backup.BackupError):restore.restore_database(self.source,self.root/'invalid.sqlite3')
        self.assertFalse((self.root/'invalid.sqlite3').exists())
        with database(self.source) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM auth_sessions').fetchone()[0],1)

    def test_rejects_invalid_sqlite_and_dangling_target_symlink(self):
        invalid=self.root/'not-sqlite';invalid.write_bytes(b'not a database')
        with self.assertRaises(backup.BackupError):restore.restore_database(invalid,self.root/'bad.sqlite3')
        destination=self.root/'symlink.sqlite3';destination.symlink_to(self.root/'missing')
        with self.assertRaises(backup.BackupError):restore.restore_database(self.source,destination)
        self.assertTrue(destination.is_symlink())
        self.assertFalse((self.root/'missing').exists())

    def test_missing_source_sidecars_and_invalid_timeout_are_rejected(self):
        with self.assertRaises(backup.BackupError):backup.backup_database(self.root/'missing',self.root/'new.sqlite3')
        self.assertFalse((self.root/'missing').exists())
        (self.root/'sidecar.sqlite3-wal').write_bytes(b'existing WAL')
        with self.assertRaises(backup.BackupError):restore.restore_database(self.source,self.root/'sidecar.sqlite3')
        for timeout in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(backup.BackupError):restore.restore_database(self.source,self.root/'new.sqlite3',timeout)

    def test_online_wal_backup_includes_committed_rows(self):
        writer=sqlite3.connect(self.source)
        try:
            writer.execute('PRAGMA journal_mode=WAL')
            writer.execute("UPDATE users SET name='Запись из WAL'");writer.commit()
            result=backup.backup_database(self.source,self.root/'online.sqlite3')
            with database(result['destination']) as conn:
                self.assertEqual(conn.execute('SELECT name FROM users').fetchone()[0],'Запись из WAL')
                self.assertEqual(conn.execute('PRAGMA journal_mode').fetchone()[0],'delete')
        finally:writer.close()

    def test_cli_roundtrip_and_nonzero_exit_on_overwrite(self):
        archived=self.root/'cli-backup.sqlite3';restored=self.root/'cli-restored.sqlite3'
        for script,source,target in [('backup.py',self.source,archived),('restore.py',archived,restored)]:
            result=subprocess.run([sys.executable,str(ROOT/'scripts'/script),'--source',str(source),'--destination',str(target)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['destination'],str(target.resolve()))
        rejected=subprocess.run([sys.executable,str(ROOT/'scripts/restore.py'),'--source',str(archived),'--destination',str(restored)],capture_output=True,text=True)
        self.assertNotEqual(rejected.returncode,0)
        self.assertIn('already exists',rejected.stderr)

    def test_actual_application_roundtrip_invalidates_old_cookie(self):
        interpreter=ROOT/'backend/.venv/bin/python'
        if not interpreter.exists():self.skipTest('Install backend .venv to run the actual application/cookie roundtrip.')
        program=r'''
import json,sys,sqlite3
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import Settings,BACKEND_DIR
from app.main import create_app
from scripts.backup import backup_database
from scripts.restore import restore_database
folder=Path(sys.argv[1]);source=folder/'actual.sqlite3'
settings=Settings(database_url=f'sqlite:///{source}',demo_mode=True,data_dir=BACKEND_DIR/'data',ai_endpoint=None,ai_mode='rules',backup_dir=folder/'unused')
app=create_app(settings)
with TestClient(app) as lifetime:
    teacher=TestClient(app);student=TestClient(app)
    assert teacher.post('/api/auth/login',json={'username':'teacher','password':'Demo112!'}).status_code==200
    assert student.post('/api/auth/login',json={'username':'student','password':'Demo112!'}).status_code==200
    cookie=student.cookies.get(settings.cookie_name)
    uid=student.get('/api/auth/me').json()['id']
    scenario=teacher.get('/api/scenarios').json()[0]
    attempt=teacher.post('/api/sessions',json={'scenario_id':scenario['id'],'student_ids':[uid],'mode':'practice'}).json()[0]
    sid=attempt['id']
    assert student.post(f'/api/sessions/{sid}/start',json={}).status_code==200
    payload={'client_event_id':'restore-test-1','kind':'status_changed','payload':{'status':'accepted','comment':'Проверяемый текст полного восстановления'}}
    assert student.post(f'/api/sessions/{sid}/events',json=payload).status_code==200
    original=student.post(f'/api/sessions/{sid}/submit',json={}).json()
    reviewed=teacher.post(f'/api/sessions/{sid}/review',json={'score':71,'comment':'Сохранить причину оценки при восстановлении'}).json()
    b=backup_database(source,folder/'actual-backup.sqlite3')
    r=restore_database(folder/'actual-backup.sqlite3',folder/'actual-restored.sqlite3')
    # Original live application remains logged in: restore did not revoke its sessions.
    assert student.get('/api/auth/me').status_code==200
    teacher.close();student.close()
restored_app=create_app(Settings(database_url=f'sqlite:///{folder/"actual-restored.sqlite3"}',demo_mode=True,data_dir=BACKEND_DIR/'data',ai_endpoint=None,ai_mode='rules'))
with TestClient(restored_app) as restored:
    restored.cookies.set(settings.cookie_name,cookie)
    assert restored.get('/api/auth/me').status_code==401
    restored.cookies.clear()
    assert restored.post('/api/auth/login',json={'username':'student','password':'Demo112!'}).status_code==200
    after=restored.get(f'/api/sessions/{sid}').json()
    assert after['report']==reviewed['report']
    assert after['events']==reviewed['events']
    assert any('Проверяемый текст' in e['payload'].get('comment','') for e in after['events'])
    assert after['report']['teacher_review']['comment']=='Сохранить причину оценки при восстановлении'
assert r['auth_sessions_removed']>=2
assert r['counts_after']['auth_sessions']==0
assert all(r['counts_after'][t]==b['counts_after'][t] for t in b['counts_after'] if t!='auth_sessions')
print(json.dumps({'old_cookie_status':401,'new_login_status':200,'counts':r['counts_after'],'tokens_removed':r['auth_sessions_removed'],'report_preserved':True}))
'''
        env=os.environ.copy();env['PYTHONPATH']=str(ROOT)+os.pathsep+str(ROOT/'backend')
        result=subprocess.run([str(interpreter),'-c',program,str(self.root)],capture_output=True,text=True,env=env,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['old_cookie_status'],401)
        self.assertTrue(report['report_preserved'])
        self.assertEqual(report['counts']['training_sessions'],1)


if __name__=='__main__':unittest.main()
