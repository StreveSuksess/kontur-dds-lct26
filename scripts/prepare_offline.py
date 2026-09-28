#!/usr/bin/env python3
"""Prepare hash-pinned wheels and built frontend for this host; requires network."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def clean_env():
    # Never inherit trusted-host/no-verify/index credentials or dotenv files.
    env={k:v for k,v in os.environ.items() if not k.startswith(('PIP_','UV_'))}
    env['PIP_CONFIG_FILE']=os.devnull
    return env


def interpreter_info(python):
    code="import json,platform,sys; print(json.dumps({'python':platform.python_version(),'major_minor':list(sys.version_info[:2]),'system':platform.system(),'machine':platform.machine(),'implementation':platform.python_implementation()}))"
    return json.loads(subprocess.check_output([python,'-I','-c',code],text=True))


def run(args,env=None):
    subprocess.run([str(x) for x in args],env=env or clean_env(),check=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python',default=sys.executable,help='Installed CPython 3.12 interpreter (no runtime download)')
    parser.add_argument('--destination',type=Path,default=ROOT/'runtime/offline-wheelhouse',help='New bundle directory; never overwrite')
    parser.add_argument('--cert',type=Path,help='Optional trusted CA PEM; TLS verification remains enabled')
    args=parser.parse_args()
    info=interpreter_info(args.python)
    if info['major_minor']!=[3,12] or info['implementation']!='CPython':raise ValueError('Use an installed CPython 3.12 interpreter with ensurepip.')
    if not (ROOT/'frontend/dist/index.html').is_file():raise ValueError('Build frontend/dist online first; this script does not run npm.')
    target=args.destination.expanduser().absolute()
    if os.path.lexists(target):raise ValueError('Destination already exists; choose a new bundle directory.')
    target.parent.mkdir(parents=True,exist_ok=True)
    lock=ROOT/'backend/uv.lock';lock_hash=sha256(lock)
    with tempfile.TemporaryDirectory(prefix='.offline-prepare-',dir=target.parent) as temporary:
        work=Path(temporary);bundle=work/'bundle';bundle.mkdir();wheels=bundle/'wheels';wheels.mkdir()
        requirements=bundle/'requirements.txt'
        subprocess.run(['uv','export','--project',str(ROOT/'backend'),'--frozen','--offline','--no-emit-project','--no-annotate','--no-header','--output-file',str(requirements)],env=clean_env(),stdout=subprocess.DEVNULL,check=True)
        # Refuse local/VCS/direct URL dependencies that could sidestep offline index rules.
        for line in requirements.read_text().splitlines():
            if line and not line[0].isspace() and not line.startswith('#') and ('==' not in line or '://' in line or ' @ ' in line):
                raise ValueError('Export contains a non-pinned or direct dependency; inspect the lockfile.')
        bootstrap=work/'download-venv'
        run([args.python,'-I','-m','venv',bootstrap])
        pip_python=bootstrap/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        command=[pip_python,'-I','-m','pip','--disable-pip-version-check']
        if args.cert:command+=['--cert',args.cert.resolve(strict=True)]
        command+=['download','--index-url','https://pypi.org/simple','--require-hashes','--only-binary=:all:','--no-cache-dir','--dest',wheels,'--requirement',requirements]
        run(command)
        shutil.copytree(ROOT/'frontend/dist',bundle/'frontend-dist')
        if sha256(lock)!=lock_hash:raise ValueError('Lockfile changed during preparation; retry with stable inputs.')
        files={str(path.relative_to(bundle)):sha256(path) for path in sorted(bundle.rglob('*')) if path.is_file()}
        manifest={'format':'dds-offline-v1','prepared_at':datetime.now(timezone.utc).isoformat(),'target':info,'uv_lock_sha256':lock_hash,'pyproject_sha256':sha256(ROOT/'backend/pyproject.toml'),'includes_dev_dependencies':True,'wheel_count':len(list(wheels.glob('*.whl'))),'files':files,'notes':['CPython runtime, source code, app data JSON and optional AI weights are not included.','Only this host platform is selected by pip; other platforms require separate preparation and validation.']}
        (bundle/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        # mkdir is the no-overwrite guard. A failed copy remains visibly incomplete,
        # and install rejects a missing/mismatched manifest instead of using it.
        target.mkdir()
        try:shutil.copytree(bundle,target,dirs_exist_ok=True)
        except BaseException:shutil.rmtree(target);raise
    print(json.dumps({'bundle':str(target),'wheel_count':manifest['wheel_count'],'target':info,'bytes':sum(p.stat().st_size for p in target.rglob('*') if p.is_file())},ensure_ascii=False))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,subprocess.CalledProcessError) as error:
        print(f'ERROR: {error}',file=sys.stderr);raise SystemExit(1)
