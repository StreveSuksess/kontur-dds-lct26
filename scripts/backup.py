#!/usr/bin/env python3
"""Create a validated SQLite backup in a new file, using only the standard library.

The final path is published atomically and cannot overwrite an existing file.
See docs/backup-restore.md for the supported schema and operational boundaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Callable

SCHEMA_VERSION = 'dds-sqlite-v2'
EXPECTED_COLUMNS = {
    'users': {'id','username','name','password_hash','role','service','group_name','active'},
    'auth_sessions': {'token_hash','user_id','expires_at'},
    'scenarios': {'id','owner_id','is_seed','status','version','data','created_at','updated_at'},
    'training_sessions': {'id','scenario_id','student_id','teacher_id','mode','status','snapshot','assigned_at','started_at','finished_at','current_status','draft','report'},
    'events': {'id','session_id','client_event_id','kind','at','elapsed_seconds','payload','sequence','request_hash','response_cache'},
    'audit': {'id','actor_id','action','entity_type','entity_id','at','details'},
    'intake112_attempts': {'id','case_id','student_id','group_name','created_at','submitted_at','card','comparison','review_comment','reviewed_at','reviewed_by'},
}
EXPECTED_FOREIGN_KEYS = {
    'users': set(),
    'auth_sessions': {('user_id','users','id')},
    'scenarios': {('owner_id','users','id')},
    'training_sessions': {('scenario_id','scenarios','id'),('student_id','users','id'),('teacher_id','users','id')},
    'events': {('session_id','training_sessions','id')},
    'audit': {('actor_id','users','id')},
    'intake112_attempts': {('student_id','users','id'),('reviewed_by','users','id')},
}
EXPECTED_PRIMARY_KEYS = {table: ('token_hash' if table=='auth_sessions' else 'id') for table in EXPECTED_COLUMNS}


class BackupError(Exception):
    """A safe operational failure, suitable for reporting without database contents."""


def validate_database(connection: sqlite3.Connection) -> dict[str,int]:
    """Reject foreign/corrupt schemas before any restored data can be published.

    Column additions intentionally need an explicit schema-version update. Triggers
    and views are unsupported; in particular, no imported trigger may run when
    restore deletes authentication sessions.
    """
    objects=connection.execute("SELECT type,name FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'").fetchall()
    tables={name for kind,name in objects if kind=='table'}
    if tables != set(EXPECTED_COLUMNS):
        raise BackupError('Unsupported database schema: expected exactly the seven current training tables.')
    if any(kind in {'trigger','view'} for kind,_ in objects):
        raise BackupError('Unsupported database schema: triggers and views are not allowed.')
    for table,expected in EXPECTED_COLUMNS.items():
        columns=connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        if {c[1] for c in columns} != expected:
            raise BackupError(f'Unsupported columns in table {table}; use a matching application/schema version.')
        primary=[c[1] for c in columns if c[5]]
        if primary != [EXPECTED_PRIMARY_KEYS[table]]:
            raise BackupError(f'Unsupported primary key in table {table}.')
        foreign={(r[3],r[2],r[4]) for r in connection.execute(f'PRAGMA foreign_key_list("{table}")')}
        if foreign != EXPECTED_FOREIGN_KEYS[table]:
            raise BackupError(f'Foreign-key schema mismatch in table {table}.')
    # Both invariants are relied upon by authentication and event idempotency.
    for table,expected in [('users',('username',)),('events',('session_id','client_event_id'))]:
        unique=[]
        for index in connection.execute(f'PRAGMA index_list("{table}")'):
            if index[2]:
                escaped=index[1].replace('"','""')
                columns=tuple(r[2] for r in connection.execute(f'PRAGMA index_info("{escaped}")'))
                if not index[4]:unique.append(columns)  # A partial index does not prove global uniqueness.
        if expected not in unique:
            raise BackupError(f'Required unique index missing in table {table}.')
    result=[r[0] for r in connection.execute('PRAGMA integrity_check')]
    if result!=['ok']:
        raise BackupError('SQLite integrity_check failed. No destination was published.')
    if connection.execute('PRAGMA foreign_key_check').fetchone() is not None:
        raise BackupError('SQLite foreign_key_check failed. No destination was published.')
    return {table:connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in EXPECTED_COLUMNS}


def checked_paths(source: str | Path,destination: str | Path) -> tuple[Path,Path]:
    source_input=Path(source).expanduser()
    if source_input.is_symlink():
        raise BackupError('Source symlinks are not accepted; provide the actual database path.')
    try:source_path=source_input.resolve(strict=True)
    except OSError as exc:raise BackupError('Source database does not exist.') from exc
    if not source_path.is_file():raise BackupError('Source must be an existing regular SQLite file.')
    target=Path(destination).expanduser()
    # Resolve only the parent. Resolving the complete target could follow an existing symlink.
    try:parent=target.parent.resolve(strict=True)
    except OSError as exc:raise BackupError('Destination directory must already exist.') from exc
    if not parent.is_dir():raise BackupError('Destination parent is not a directory.')
    target=parent/target.name
    if os.path.lexists(target):raise BackupError('Destination already exists; overwrite is never allowed.')
    if target==source_path:raise BackupError('Source and destination must differ.')
    for suffix in ('-wal','-shm','-journal'):
        if os.path.lexists(str(target)+suffix):
            raise BackupError('SQLite sidecar already exists at destination; choose a fresh path.')
    return source_path,target


def fsync_file(path:Path) -> None:
    with path.open('rb') as handle:os.fsync(handle.fileno())


def publish_new_file(temp:Path,destination:Path) -> None:
    """Atomic no-clobber publication on the same filesystem.

    POSIX rename/replace can overwrite a path created after an existence check.
    link() atomically creates a final name or fails with EEXIST. Removing the
    temporary name afterwards is equivalent to a no-replace rename for readers.
    """
    try:os.link(temp,destination,follow_symlinks=False)
    except FileExistsError as exc:raise BackupError('Destination appeared concurrently; nothing was overwritten.') from exc
    except OSError as exc:raise BackupError('Atomic publication failed; destination filesystem must support hard links.') from exc
    temp.unlink()
    directory_fd=os.open(destination.parent,os.O_RDONLY)
    try:os.fsync(directory_fd)
    finally:os.close(directory_fd)


def copy_database(source: str | Path,destination: str | Path,*,clear_auth_sessions:bool=False,timeout_seconds:float=60) -> dict:
    if not math.isfinite(timeout_seconds) or timeout_seconds<=0 or timeout_seconds>3600:
        raise BackupError('Timeout must be greater than 0 and at most 3600 seconds.')
    source_path,target=checked_paths(source,destination)
    deadline=time.monotonic()+timeout_seconds
    def expired():return time.monotonic()>deadline
    def progress(status,remaining,total):
        if expired():raise BackupError('Copy timed out; no destination was published.')
    fd,temp_name=tempfile.mkstemp(prefix='.'+target.name+'.',suffix='.tmp',dir=target.parent)
    os.close(fd);temp=Path(temp_name)
    counts_before={};counts_after={};removed=0
    try:
        # mode=ro never creates a missing source and cannot change its rows/schema.
        with sqlite3.connect(source_path.as_uri()+'?mode=ro',uri=True,timeout=5) as origin:
            origin.execute('PRAGMA query_only=ON')
            origin.execute('PRAGMA trusted_schema=OFF')
            origin.set_progress_handler(lambda:1 if expired() else 0,10000)
            with sqlite3.connect(temp,timeout=5) as copied:
                copied.execute('PRAGMA trusted_schema=OFF')
                copied.execute('PRAGMA foreign_keys=ON')
                origin.backup(copied,pages=256,progress=progress,sleep=0.01)
                copied.set_progress_handler(lambda:1 if expired() else 0,10000)
                counts_before=validate_database(copied)
                if clear_auth_sessions:
                    removed=counts_before['auth_sessions']
                    copied.execute('DELETE FROM auth_sessions')
                    copied.commit()
                # Make the result self-contained: no WAL sidecars are needed when moved.
                copied.execute('PRAGMA wal_checkpoint(TRUNCATE)')
                copied.execute('PRAGMA journal_mode=DELETE')
                counts_after=validate_database(copied)
                if clear_auth_sessions and counts_after['auth_sessions']!=0:
                    raise BackupError('Authentication-session removal could not be verified.')
        # sqlite3.Connection context commits but does not close the object.
        origin.close();copied.close()
        os.chmod(temp,0o600)
        fsync_file(temp)
        with temp.open('rb') as handle:
            digest=hashlib.file_digest(handle,'sha256').hexdigest()
        size=temp.stat().st_size
        publish_new_file(temp,target)
        return {'operation':'restore' if clear_auth_sessions else 'backup','schema':SCHEMA_VERSION,'source':str(source_path),'destination':str(target),'bytes':size,'sha256':digest,'counts_before':counts_before,'counts_after':counts_after,'auth_sessions_removed':removed}
    except sqlite3.Error as exc:
        raise BackupError('SQLite validation/copy failed; source is unchanged and no incomplete destination was published.') from exc
    finally:
        # Close on failure as well, before removing temporary sidecars (important on Windows).
        for conn in (locals().get('origin'),locals().get('copied')):
            if conn is not None:conn.close()
        temp.unlink(missing_ok=True)
        for suffix in ('-wal','-shm','-journal'):
            Path(str(temp)+suffix).unlink(missing_ok=True)


def backup_database(source: str | Path,destination: str | Path,timeout_seconds:float=60) -> dict:
    return copy_database(source,destination,clear_auth_sessions=False,timeout_seconds=timeout_seconds)


def run_cli(operation:Callable,description:str) -> int:
    parser=argparse.ArgumentParser(description=description)
    parser.add_argument('--source',required=True,type=Path,help='Existing SQLite database/backup file')
    parser.add_argument('--destination',required=True,type=Path,help='New file in an existing directory; no overwrite option')
    parser.add_argument('--timeout',type=float,default=60,help='Time budget in seconds (default 60, max 3600)')
    args=parser.parse_args()
    try:result=operation(args.source,args.destination,timeout_seconds=args.timeout)
    except (BackupError,OSError) as exc:
        import sys
        print(f'ERROR: {exc}',file=sys.stderr)
        return 1
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(run_cli(backup_database,'Create and validate a DDS SQLite backup in a NEW file.'))
