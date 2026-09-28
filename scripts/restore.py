#!/usr/bin/env python3
"""Restore a DDS SQLite backup ONLY to a new database, invalidating login cookies."""
from __future__ import annotations
from pathlib import Path

try:  # Importable in pytest and executable directly as python scripts/restore.py.
    from .backup import copy_database,run_cli
except ImportError:
    from backup import copy_database,run_cli


def restore_database(source:str | Path,destination:str | Path,timeout_seconds:float=60) -> dict:
    return copy_database(source,destination,clear_auth_sessions=True,timeout_seconds=timeout_seconds)


if __name__=='__main__':
    raise SystemExit(run_cli(restore_database,'Restore a validated DDS SQLite backup to a NEW database; clear authentication sessions.'))
