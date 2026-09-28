#!/usr/bin/env python3
"""Refresh a verified wheelhouse without network; package it with a source ZIP."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

try:
    from .package_release import PREFIX, FIXED_TIME, PackageError, safe_path, selected, security_scan, validate_archive
    from .prepare_offline import ROOT
except ImportError:
    from package_release import PREFIX, FIXED_TIME, PackageError, safe_path, selected, security_scan, validate_archive
    from prepare_offline import ROOT

MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 192 * 1024 * 1024
BUNDLE_PREFIX = 'runtime/offline-wheelhouse/'
OFFLINE_MANIFEST = 'OFFLINE-PACKAGE-MANIFEST.json'
README = '''# Контур ДДС — офлайн-комплект macOS arm64

Распакуйте ZIP в НОВЫЙ каталог и откройте терминал в `kontur-dds`.
В комплекте исходники, готовый интерфейс, 31 Python wheel и точные требования.
**Заранее нужен CPython 3.12 с venv/ensurepip для macOS arm64.** Python runtime,
AI runtime/веса, рабочая БД, cookie и настоящие .env не включены. Node/npm/uv
для этой установки не нужны. Linux/Windows этим комплектом не проверены.

Первая установка без интернета (существующий venv не перезаписывается):

```sh
python3.12 scripts/install_offline.py --python python3.12 \\
  --bundle runtime/offline-wheelhouse --venv backend/.venv --smoke
```

Первый демонстрационный запуск, из корня распакованного `kontur-dds`:

```sh
DDS_PROJECT_DIR="$PWD"
export STATIC_DIR="$DDS_PROJECT_DIR/runtime/offline-wheelhouse/frontend-dist"
export DATABASE_URL="sqlite:///$DDS_PROJECT_DIR/backend/var/offline-demo.db"
export DEMO_MODE=true
export AI_MODE=rules
export AI_ENDPOINT=""
export ALLOWED_ORIGINS="http://localhost:8000,http://127.0.0.1:8000"
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Откройте http://127.0.0.1:8000. Демонстрационный пароль для `student`, `teacher`
и `admin`: `Demo112!`. Это публичные синтетические аккаунты, не production.
Новая БД создаётся при первом запуске; прежние рабочие данные не передаются.
Текстовый учебный цикл доступен без моделей. Голосовой AI требует отдельной
подготовки; встроенные WAV не являются моделями или реальной телефонией.

Подробности и ограничения: `docs/offline-install.md` и
`docs/offline-distribution.md`. Python-блокировка сети в smoke не равна
физическому отключению сети ОС или испытанию учебного класса.

`PACKAGE-MANIFEST.json` и `OFFLINE-PREREQUISITES.txt` сохранены из исходного
source ZIP и описывают только исходную часть поставки. Дополнения текущего
комплекта перечислены вместе с исходниками в `OFFLINE-PACKAGE-MANIFEST.json`.
`runtime/offline-wheelhouse/manifest.json` содержит хеши зависимостей и статики.
SHA-256 обнаруживает изменение, но не является подписью доверенного издателя.
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def regular_bytes(path: Path, root: Path):
    relative = path.relative_to(root)
    if root.is_symlink() or any((root.joinpath(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)):
        raise PackageError('Symlink in input tree')
    if not path.is_file() or path.stat().st_size > MAX_FILE:
        raise PackageError('Missing, non-regular or oversized input file')
    return path.read_bytes()


def load_bundle(bundle: Path):
    raw = regular_bytes(bundle/'manifest.json', bundle)
    security_scan('manifest.json', raw)
    manifest = json.loads(raw)
    if manifest.get('format') != 'dds-offline-v1':
        raise PackageError('Unknown wheelhouse format')
    target = manifest.get('target', {})
    if any(target.get(k) != v for k, v in {'major_minor':[3,12], 'implementation':'CPython', 'system':'Darwin', 'machine':'arm64'}.items()):
        raise PackageError('This release packager accepts only CPython 3.12 macOS arm64')
    files = {}
    for name, expected in manifest['files'].items():
        parts = safe_path(name).parts
        allowed = name == 'requirements.txt' or (len(parts) == 2 and parts[0] == 'wheels' and name.endswith('.whl')) or (name.startswith('frontend-dist/') and selected('frontend/dist/' + name.removeprefix('frontend-dist/')))
        if not allowed:
            raise PackageError('Disallowed wheelhouse member: ' + name)
        data = regular_bytes(bundle.joinpath(*parts), bundle)
        if digest(data) != expected:
            raise PackageError('Wheelhouse checksum mismatch: ' + name)
        if name == 'requirements.txt' or name.startswith('frontend-dist/'):
            security_scan(name, data)
        files[name] = data
    actual = set()
    for path in bundle.rglob('*'):
        if path.is_symlink():
            raise PackageError('Symlink in wheelhouse')
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
        elif not path.is_dir():
            raise PackageError('Special file in wheelhouse')
    if actual != set(files) | {'manifest.json'}:
        raise PackageError('Wheelhouse contains unmanifested files')
    wheels = [name for name in files if name.startswith('wheels/')]
    if len(wheels) != manifest['wheel_count'] or not wheels or not {'requirements.txt','frontend-dist/index.html'} <= set(files):
        raise PackageError('Incomplete wheelhouse')
    if sum(map(len, files.values())) > MAX_TOTAL:
        raise PackageError('Wheelhouse exceeds size cap')
    files['manifest.json'] = raw
    return manifest, files


def refresh_bundle(bundle: Path, destination: Path, root: Path = ROOT):
    """Reuse only already verified pinned wheels; snapshot frozen frontend locally."""
    if os.path.lexists(destination):
        raise PackageError('Refresh destination already exists')
    manifest, old_files = load_bundle(bundle)
    for name, key in [('backend/uv.lock','uv_lock_sha256'),('backend/pyproject.toml','pyproject_sha256')]:
        if digest(regular_bytes(root/name, root)) != manifest[key]:
            raise PackageError('Dependencies changed; fresh online preparation is required')
    files = {name:data for name,data in old_files.items() if name == 'requirements.txt' or name.startswith('wheels/')}
    for path in sorted((root/'frontend/dist').rglob('*')):
        if path.is_symlink():
            raise PackageError('Symlink in frontend build')
        if path.is_file():
            source_name = path.relative_to(root).as_posix()
            if not selected(source_name):
                raise PackageError('Unexpected frontend build member')
            data = regular_bytes(path, root)
            security_scan(source_name, data)
            files['frontend-dist/' + path.relative_to(root/'frontend/dist').as_posix()] = data
    if 'frontend-dist/index.html' not in files:
        raise PackageError('Frontend build is missing')
    updated = dict(manifest, refreshed_at=datetime.now(timezone.utc).isoformat(), reused_dependencies_without_network=True,
                   files={name:digest(data) for name,data in sorted(files.items())})
    files['manifest.json'] = encoded(updated)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()  # no-overwrite claim, also if another writer won the race
    try:
        for name,data in files.items():
            path = destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        load_bundle(destination)
    except BaseException:
        shutil.rmtree(destination)
        raise
    return {'bundle':destination.name,'wheel_count':updated['wheel_count'],'bytes':sum(map(len,files.values())),
            'frontend_index_sha256':updated['files']['frontend-dist/index.html'],'network_used':False}


def load_source(source: Path):
    if source.is_symlink() or source.stat().st_size > MAX_TOTAL:
        raise PackageError('Unsafe source archive input')
    blob = source.read_bytes()
    files = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = archive.infolist()
        if sum(i.file_size for i in entries) > MAX_TOTAL:
            raise PackageError('Source archive exceeds size cap')
        for info in entries:
            parts = safe_path(info.filename).parts
            if len(parts) < 2 or parts[0] != PREFIX or info.file_size > MAX_FILE or info.flag_bits & 1:
                raise PackageError('Unsafe or oversized source archive member')
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG) or info.is_dir():
                raise PackageError('Non-regular source archive member')
            name = '/'.join(parts[1:])
            if name in files:
                raise PackageError('Duplicate source archive member')
            files[name] = archive.read(info)
    manifest = json.loads(files['PACKAGE-MANIFEST.json'])
    if manifest.get('format') != 'kontur-dds-source-package-v1':
        raise PackageError('Unknown source archive format')
    if len(manifest['entries']) != len({item['path'] for item in manifest['entries']}):
        raise PackageError('Duplicate source manifest entry')
    validate_archive(blob, manifest)
    required = {'scripts/install_offline.py','scripts/prepare_offline.py','scripts/offline_smoke.py','docs/offline-install.md'}
    if not required <= files.keys():
        raise PackageError('Source archive predates offline installer; rebuild it first')
    return files, digest(blob)


def build_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            safe_path(name)
            info = zipfile.ZipInfo(f'{PREFIX}/{name}', FIXED_TIME)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def publish_new(path: Path, data: bytes):
    """Publish a complete file atomically without overwriting even a racing writer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.offline-package-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)  # fails if destination exists; no replace/force
    finally:
        Path(temporary).unlink(missing_ok=True)


def package(source: Path, bundle: Path, output: Path):
    report_path = output.with_suffix('.validation.json')
    if os.path.lexists(output) or os.path.lexists(report_path):
        raise PackageError('Output or validation report already exists; choose a new filename')
    files, source_hash = load_source(source)
    manifest, wheel_files = load_bundle(bundle)
    for name,key in [('backend/uv.lock','uv_lock_sha256'),('backend/pyproject.toml','pyproject_sha256')]:
        if digest(files[name]) != manifest[key]:
            raise PackageError('Source ZIP dependencies differ from wheelhouse')
    source_frontend = {name.removeprefix('frontend/dist/'):data for name,data in files.items() if name.startswith('frontend/dist/')}
    bundled_frontend = {name.removeprefix('frontend-dist/'):data for name,data in wheel_files.items() if name.startswith('frontend-dist/')}
    if source_frontend != bundled_frontend:
        raise PackageError('Source ZIP frontend differs from frozen wheelhouse')
    for name,data in wheel_files.items():
        destination = BUNDLE_PREFIX + name
        if destination in files:
            raise PackageError('Source ZIP collides with offline additions')
        files[destination] = data
    if 'OFFLINE-INSTALL-README.md' in files or OFFLINE_MANIFEST in files:
        raise PackageError('Source ZIP already contains offline additions')
    files['OFFLINE-INSTALL-README.md'] = README.encode()
    full_manifest = {'format':'kontur-dds-offline-package-v1','archive_prefix':PREFIX,'source_archive_sha256':source_hash,
                     'wheelhouse_manifest_sha256':digest(wheel_files['manifest.json']),'target':manifest['target'],
                     'python_runtime_included':False,'ai_models_included':False,'working_database_included':False,
                     'entries':[{'path':name,'size':len(data),'sha256':digest(data)} for name,data in sorted(files.items())]}
    files[OFFLINE_MANIFEST] = encoded(full_manifest)
    if sum(map(len, files.values())) > MAX_TOTAL:
        raise PackageError('Final package exceeds size cap')
    blob = build_zip(files)
    if build_zip(files) != blob:
        raise PackageError('Package is not deterministic for captured inputs')
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        if archive.testzip() is not None or set(archive.namelist()) != {f'{PREFIX}/{name}' for name in files}:
            raise PackageError('Final archive integrity failed')
        for name,data in files.items():
            if archive.read(f'{PREFIX}/{name}') != data:
                raise PackageError('Final archive bytes mismatch')
    report = {'archive':output.name,'sha256':digest(blob),'archive_bytes':len(blob),'included_files':len(files),
              'source_archive_sha256':source_hash,'wheel_count':manifest['wheel_count'],'target':manifest['target'],
              'checks':{'source_manifest_and_allowlist':True,'wheelhouse_hashes_and_exact_file_set':True,
                        'frontend_identical_to_source_zip':True,'crc_and_full_byte_roundtrip':True,
                        'same_inputs_deterministic':True,'symlinks_and_traversal_rejected':True,'no_overwrite':True},
              'limits':['Python runtime and optional AI are not bundled','No Linux or Windows validation',
                        'Checksums are not a publisher signature','Packaging does not boot the application; see offline smoke evidence']}
    publish_new(output, blob)
    publish_new(report_path, encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    refresh = sub.add_parser('refresh', help='No network: pinned wheels plus current frozen frontend in NEW directory')
    refresh.add_argument('--bundle', type=Path, default=ROOT/'runtime/offline-wheelhouse')
    refresh.add_argument('--destination', type=Path, required=True)
    pack = sub.add_parser('package', help='Create NEW release ZIP only after source ZIP is final')
    pack.add_argument('--source-zip', type=Path, default=ROOT/'deliverables/kontur-dds-source.zip')
    pack.add_argument('--bundle', type=Path, required=True)
    pack.add_argument('--output', type=Path, default=ROOT/'deliverables/kontur-dds-macos-arm64-offline.zip')
    args = parser.parse_args()
    try:
        result = refresh_bundle(args.bundle.absolute(), args.destination.absolute()) if args.command == 'refresh' else package(args.source_zip.absolute(), args.bundle.absolute(), args.output.absolute())
    except (ValueError, OSError, KeyError, SyntaxError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Offline packaging failed: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
