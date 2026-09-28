#!/usr/bin/env python3
"""Install prepared wheels into a NEW venv without accessing package indexes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
try:
    from .prepare_offline import ROOT, sha256, interpreter_info, clean_env, run
except ImportError:
    from prepare_offline import ROOT, sha256, interpreter_info, clean_env, run

# Block network at the Python socket boundary in addition to pip --no-index.
OFFLINE_PIP='''
import runpy,socket,sys
calls=[]
def denied(*args,**kwargs):
    calls.append(1)
    raise RuntimeError("Network access is blocked in offline installer")
socket.socket.connect=denied
socket.socket.connect_ex=denied
socket.getaddrinfo=denied
sys.argv=["pip"]+sys.argv[1:]
runpy.run_module("pip",run_name="__main__")
'''


def validate_bundle(bundle,info):
    manifest=json.loads((bundle/'manifest.json').read_text())
    if manifest.get('format')!='dds-offline-v1':raise ValueError('Unknown offline bundle format.')
    for key in ['major_minor','system','machine','implementation']:
        if manifest['target'][key]!=info[key]:raise ValueError(f'Bundle target mismatch: {key}. Prepare wheels on the actual target platform.')
    for relative,expected in manifest['files'].items():
        path=bundle/relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()):
            raise ValueError('Unsafe bundle path.')
        if sha256(path)!=expected:raise ValueError(f'Bundle checksum mismatch: {relative}')
    if manifest['uv_lock_sha256']!=sha256(ROOT/'backend/uv.lock') or manifest['pyproject_sha256']!=sha256(ROOT/'backend/pyproject.toml'):
        raise ValueError('Source dependency manifest differs from this bundle; prepare matching artifacts.')
    if 'requirements.txt' not in manifest['files'] or 'frontend-dist/index.html' not in manifest['files']:
        raise ValueError('Incomplete bundle manifest.')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'runtime/offline-wheelhouse')
    parser.add_argument('--python',default=sys.executable,help='Already installed CPython 3.12 with ensurepip')
    parser.add_argument('--venv',type=Path,default=ROOT/'backend/.venv',help='NEW venv path; existing environments are never modified')
    parser.add_argument('--smoke',action='store_true',help='Run network-blocked lifecycle test in copied source/temp DB')
    args=parser.parse_args();bundle=args.bundle.resolve(strict=True)
    info=interpreter_info(args.python)
    if info['major_minor']!=[3,12] or info['implementation']!='CPython':raise ValueError('Use an installed CPython 3.12 interpreter.')
    manifest=validate_bundle(bundle,info)
    target=args.venv.expanduser().absolute()
    if os.path.lexists(target):raise ValueError('Venv already exists; refusing to overwrite or update it.')
    target.parent.mkdir(parents=True,exist_ok=True);target.mkdir()
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    try:
        run([args.python,'-I','-m','venv',target])
        run([python,'-I','-c',OFFLINE_PIP,'--disable-pip-version-check','install','--no-index','--no-cache-dir','--find-links',bundle/'wheels','--only-binary=:all:','--require-hashes','--requirement',bundle/'requirements.txt'])
        run([python,'-I','-m','pip','--disable-pip-version-check','check'])
    except BaseException:
        shutil.rmtree(target);raise
    if args.smoke:run([python,'-I',ROOT/'scripts/offline_smoke.py','--bundle',bundle])
    print(json.dumps({'installed_venv':str(target),'python':str(python),'frontend_dist':str(bundle/'frontend-dist'),'network_policy':'pip --no-index plus blocked socket.connect/connect_ex/getaddrinfo','wheel_count':manifest['wheel_count'],'smoke_requested':args.smoke},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}',file=sys.stderr);raise SystemExit(1)
