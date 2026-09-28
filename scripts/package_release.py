#!/usr/bin/env python3
"""Create an inspected, deterministic source/demo ZIP; standard library only.

Dependency environments, models and working databases are intentionally absent.
The package is a source snapshot with compiled browser assets, not an installer.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
import zipfile

PREFIX = 'kontur-dds'
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 96 * 1024 * 1024
ROOT_FILES = {'README.md', '.gitignore', '.dockerignore', '.env.example', 'Dockerfile', 'compose.yaml'}
BACKEND_FILES = {'backend/README.md', 'backend/pyproject.toml', 'backend/uv.lock', 'backend/.env.example'}
FRONTEND_FILES = {'frontend/package.json', 'frontend/package-lock.json', 'frontend/tsconfig.json', 'frontend/vite.config.ts', 'frontend/index.html'}
DATA_FILES = {'backend/data/classifier.json', 'backend/data/knowledge.json', 'backend/data/scenarios.json'}
SCREENSHOTS = {'deliverables/assets/workspace-viewport.png', 'deliverables/assets/report-evidence.png',
               'deliverables/assets/teacher-overview.png', 'deliverables/assets/scenario-review.png',
               'deliverables/assets/teacher-observation.png', 'deliverables/assets/asr-draft.png',
               'deliverables/assets/rc3-preview-desktop.png', 'deliverables/assets/rc3-preview-mobile.png',
               'deliverables/assets/rc3-report-first-decision.png', 'deliverables/assets/rc3-recommendation-match.png'}
RESEARCH_NOTES = {'2026-09-19-product-discovery.md', '2026-09-19-market-research.md',
                  '2026-09-19-evaluation-design.md', '2026-09-19-qa-and-feasibility.md',
                  '2026-09-26-additional-materials.md', '2026-09-26-learning-feedback-research.md',
                  '2026-09-26-teacher-workflow-audit.md', '2026-09-28-chat-qa-audit.md'}
MODEL_COMPARISON_EVIDENCE = {'preregistration.json', 'holdout.json', 'system-prompt.txt',
                             'report-method.md', 'source-manifest.json', 'toolchain.json'}
PILOT_TEMPLATES = {'README.md', 'preregistration.md', 'adjudication.csv',
                   'observations.csv', 'task-outcomes.csv', 'time-cost.csv'}
DENIED_PARTS = {'.git', 'node_modules', '.venv', '.venv-asr', '__pycache__', '.pytest_cache', '.ruff_cache',
                'runtime', 'models', 'backups', 'downloads', 'var', 'playwright-report', 'test-results'}
DENIED_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.pyc', '.pyo', '.pem', '.key', '.p12', '.pfx', '.pt', '.gguf', '.safetensors', '.zip'}
TEXT_SUFFIXES = {'.py', '.sh', '.mjs', '.cjs', '.ts', '.tsx', '.js', '.jsx', '.css', '.html', '.json', '.md', '.toml', '.yaml', '.yml', '.lock', '.xml', '.rels'}
SECRETS = [
    ('private_key', re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')),
    ('provider_api_key', re.compile(rb'(?<![A-Za-z0-9])sk-(?:proj-)?[A-Za-z0-9_-]{32,}')),
    ('github_token', re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}')),
    ('aws_access_key', re.compile(rb'AKIA[0-9A-Z]{16}')),
    ('authenticated_http_url', re.compile(rb'https?://[^/\s:@]+:[^/\s@]+@')),
]
SYNTHETIC_FIXTURES = {'backend/tests/test_ai.py': (b'http://user:' + b'secret@localhost:80',)}
PRIVATE_HOME = re.compile(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/')
REQUIRED = {
    'README.md', 'Dockerfile', 'compose.yaml', 'scripts/start.sh', 'scripts/package_release.py',
    'backend/app/main.py', 'backend/app/config.py', 'backend/app/seed.py', 'backend/pyproject.toml', 'backend/uv.lock',
    'backend/data/classifier.json', 'backend/data/scenarios.json', 'backend/data/knowledge.json',
    'frontend/dist/index.html', 'frontend/package.json', 'frontend/package-lock.json',
    'docs/release-package.md', 'docs/demo-script.md', 'docs/coverage.md',
    'docs/product-deepening.md', 'docs/specs/targeted-practice.md',
    'frontend/src/components/ScenarioPreview.tsx',
    'research/model-comparison/preregistration.json', 'research/model-comparison/holdout.json',
    'research/model-comparison/system-prompt.txt', 'research/model-comparison/report-method.md',
    'research/model-comparison/source-manifest.json', 'research/model-comparison/toolchain.json',
    'deliverables/kontur-dds-defense-v1.pptx', 'deliverables/kontur-dds-defense-v1.pdf',
    'deliverables/kontur-dds-defense-v2.pptx', 'deliverables/kontur-dds-defense-v2.pdf',
    'deliverables/kontur-dds-documentation-v2.pdf',
    'deliverables/kontur-dds-defense-v3.pptx', 'deliverables/kontur-dds-defense-v3.pdf',
    'deliverables/kontur-dds-documentation-v3.pdf', 'deliverables/kontur-dds-demo-montage.mp4',
    'docs/prototype.md', 'docs/jury-evidence.md', 'docs/evaluation-report.md',
    'memory-bank/research/2026-09-28-chat-qa-audit.md',
}
OFFLINE_NOTICE = '''КОНТУР ДДС — СОСТАВ ПОСТАВКИ И УСЛОВИЯ ЗАПУСКА

Это снимок исходников, документации и демонстрационных материалов.
Включена готовая frontend/dist. Python, Node, uv, зависимости backend/frontend,
виртуальное окружение, Docker image, AI runtime, модели, рабочая БД и реальные
секреты НЕ включены. Архив НЕ является автономным переносимым установщиком.

Первичная подготовка с доступом к репозиториям пакетов:
  Python 3.12 или 3.13, uv, Node.js 22 и npm.
  ./scripts/start.sh
Этот путь устанавливает зависимости и пересобирает браузерную часть.

Офлайн после подготовки на совместимой целевой машине:
  ./scripts/start.sh --offline
Команда требует backend/.venv/bin/python с установленными зависимостями и
frontend/dist/index.html. Перенос готовой .venv между ОС/архитектурами не обещан.
Допустима отдельно подготовленная среда/образ для целевой ОС; её сборка и
перенос являются самостоятельным этапом. Сетевые сервисы AI опциональны.

Демонстрационные аккаунты и пароли из README — намеренно публичные синтетические
fixtures. Они не являются производственными учётными данными. Рабочие пользователи,
cookie, токены и БД не упакованы. Не включайте деморежим для реального внедрения.

Без нейросетей доступны учебный цикл, правила и текстовый доклад. Для AI нужны
отдельно подготовленные веса и runtime; см. docs/local-ai.md и docs/local-tts.md.
Включённые WAV — короткие подготовленные реплики, не модели и не SIP-интеграция.

Реестр SHA256: PACKAGE-MANIFEST.json. Исходные материалы заказчика и приватный
реестр с абсолютными путями исключены. Ссылки документации на неупакованные
исходники — ссылки на происхождение, не обещание наличия этих файлов в архиве.

Требования сдачи: репозиторий, презентация, прототип и сопроводительный DOCX/PDF.
Q&A дополнительно допускает видеопрезентацию продукта или запись экрана
со звуком до пяти минут. docs/demo-script.md — сценарий, НЕ готовая запись.
'''


class PackageError(ValueError):
    pass


def safe_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or any(p in ('', '.', '..') for p in name.split('/')):
        raise PackageError(f'Unsafe path: {name}')
    if any(ord(c) < 32 for c in name) or ':' in name:
        raise PackageError(f'Unsafe path: {name}')
    return path


def selected(name: str) -> bool:
    path = safe_path(name)
    if any(p in DENIED_PARTS or p.startswith('.env') and p != '.env.example' for p in path.parts):
        return False
    if path.suffix.lower() in DENIED_SUFFIXES or any(name.endswith(s) for s in ('-wal', '-shm', '-journal')):
        return False
    if name in ROOT_FILES | BACKEND_FILES | FRONTEND_FILES | DATA_FILES | SCREENSHOTS | {'research/README.md'}:
        return True
    if name.startswith(('backend/app/', 'backend/tests/', 'tests/')):
        return path.suffix in {'.py', '.cjs', '.js', '.mjs'}
    if name.startswith('frontend/src/'):
        return path.suffix in {'.ts', '.tsx', '.css', '.svg'}
    if name.startswith(('frontend/public/', 'frontend/dist/')):
        return path.suffix in {'.html', '.js', '.css', '.json', '.wav', '.png', '.svg', '.ico', '.woff', '.woff2'}
    if name.startswith('scripts/'):
        return path.suffix in {'.py', '.sh', '.mjs', '.cjs'}
    if name.startswith('docs/') and len(path.parts) == 2:
        return path.suffix in {'.md', '.json'} and path.name not in {'release-package-validation.json', 'release-package-manifest.json'}
    if name in {'docs/specs/criterion-review.md', 'docs/specs/targeted-practice.md'}:
        return True
    if len(path.parts) == 3 and path.parts[:2] == ('docs', 'pilot-templates'):
        return path.name in PILOT_TEMPLATES
    if name.startswith('memory-bank/research/') and len(path.parts) == 3:
        return path.name in RESEARCH_NOTES
    if len(path.parts) == 3 and path.parts[:2] == ('research', 'model-comparison'):
        return path.name in MODEL_COMPARISON_EVIDENCE
    if name.startswith('memory-bank/decisions/') and len(path.parts) == 3:
        return path.suffix == '.md'
    if name in {'deliverables/README.md', 'deliverables/kontur-dds-guide.pdf', 'deliverables/kontur-dds-demo-montage.mp4'}:
        return True
    return bool(re.fullmatch(r'deliverables/kontur-dds-(?:defense-v[0-9]+|documentation-v[0-9]+)\.(?:pptx|pdf)', name))


def security_scan(name: str, data: bytes) -> None:
    screened = data
    for fixture in SYNTHETIC_FIXTURES.get(name, ()):
        screened = screened.replace(fixture, b'<documented-synthetic-test-fixture>')
    for label, pattern in SECRETS:
        if pattern.search(screened):
            raise PackageError(f'Secret-like material ({label}) in {name}; matched bytes withheld')
    if PRIVATE_HOME.search(data):
        raise PackageError(f'Private absolute home path in {name}; use relative documentation/code paths')
    if name.endswith('.pptx'):
        with zipfile.ZipFile(io.BytesIO(data)) as inner:
            for info in inner.infolist():
                safe_path(info.filename.rstrip('/'))
                if info.file_size > MAX_FILE_BYTES:
                    raise PackageError(f'Oversized PPTX member: {name}')
                if info.filename.endswith(('.xml', '.rels')):
                    security_scan(name + '::' + info.filename, inner.read(info))


def collect(root: Path) -> tuple[dict[str, bytes], list[dict]]:
    files: dict[str, bytes] = {}
    transformed = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        rel_dir = Path(directory).relative_to(root)
        # Only the explicitly allowlisted synthetic model evidence is traversed
        # under research; raw customer files and private provenance stay out.
        dirs[:] = sorted(d for d in dirs if d not in DENIED_PARTS and not d.startswith('.venv') and
                         not (rel_dir == Path('research') and d != 'model-comparison'))
        for filename in sorted(names):
            path = Path(directory) / filename
            relative = path.relative_to(root).as_posix()
            if not selected(relative):
                continue
            if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != root.parent):
                raise PackageError(f'Symlink is not packaged: {relative}')
            before = path.stat()
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE_BYTES:
                raise PackageError(f'Non-regular or oversized file: {relative}')
            data = path.read_bytes()
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise PackageError(f'File changed during snapshot: {relative}; rerun when edits finish')
            if path.suffix == '.md':
                text = data.decode('utf-8')
                clean = text.replace(str(root), '.').replace(str(Path.home()), '<USER_HOME>')
                if clean != text:
                    transformed.append({'path': relative, 'operation': 'private_absolute_paths_to_relative_or_placeholder',
                                        'source_sha256': hashlib.sha256(data).hexdigest()})
                data = clean.encode('utf-8')
            security_scan(relative, data)
            files[relative] = data
    missing = REQUIRED - files.keys()
    if missing:
        raise PackageError('Required source files missing: ' + ', '.join(sorted(missing)))
    if sum(map(len, files.values())) > MAX_TOTAL_BYTES:
        raise PackageError('Source snapshot exceeds package size cap; do not add weights or raw data')
    files['OFFLINE-PREREQUISITES.txt'] = OFFLINE_NOTICE.encode('utf-8')
    return files, transformed


def make_manifest(files: dict[str, bytes], transformed: list[dict]) -> dict:
    return {'format': 'kontur-dds-source-package-v1', 'archive_prefix': PREFIX,
            'dependency_environments_included': False, 'model_weights_included': False,
            'working_database_included': False, 'synthetic_demo_credentials_included': True,
            'text_transformations': transformed,
            'entries': [{'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                         'mode': '0755' if name.endswith('.sh') else '0644'} for name, data in sorted(files.items())]}


def zip_bytes(files: dict[str, bytes], manifest: dict) -> bytes:
    payload = dict(files)
    payload['PACKAGE-MANIFEST.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            safe_path(name)
            info = zipfile.ZipInfo(f'{PREFIX}/{name}', FIXED_TIME)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | (0o755 if name.endswith('.sh') else 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def validate_archive(blob: bytes, manifest: dict) -> dict:
    expected = {entry['path']: entry for entry in manifest['entries']}
    required = REQUIRED | {'OFFLINE-PREREQUISITES.txt', 'PACKAGE-MANIFEST.json'}
    checks = {'manifest_hashes': True, 'no_unsafe_paths': True, 'no_symlinks': True,
              'required_entrypoints': True, 'python_syntax': True, 'frontend_assets': True,
              'shell_syntax': None, 'application_booted': False, 'offline_environment_bundled': False}
    with tempfile.TemporaryDirectory(prefix='kontur-package-check-') as temp:
        destination = Path(temp)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            if archive.testzip() is not None:
                raise PackageError('Archive CRC check failed')
            seen = set()
            for info in archive.infolist():
                path = safe_path(info.filename)
                if path.parts[0] != PREFIX or len(path.parts) < 2 or info.filename in seen:
                    raise PackageError('Unexpected or duplicate archive member')
                seen.add(info.filename)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise PackageError('Symlink in produced archive')
                relative = PurePosixPath(*path.parts[1:]).as_posix()
                if relative not in {'OFFLINE-PREREQUISITES.txt', 'PACKAGE-MANIFEST.json'} and not selected(relative):
                    raise PackageError('Disallowed member in archive: ' + relative)
                if relative not in expected and relative != 'PACKAGE-MANIFEST.json':
                    raise PackageError('Unmanifested archive member: ' + relative)
                data = archive.read(info)
                security_scan(relative, data)
                if relative in expected and (len(data) != expected[relative]['size'] or hashlib.sha256(data).hexdigest() != expected[relative]['sha256']):
                    raise PackageError('Manifest mismatch: ' + relative)
                target = destination.joinpath(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod((info.external_attr >> 16) & 0o777)
            if seen != {f'{PREFIX}/{name}' for name in [*expected, 'PACKAGE-MANIFEST.json']}:
                raise PackageError('Archive path set differs from complete manifest')
            if json.loads(archive.read(f'{PREFIX}/PACKAGE-MANIFEST.json')) != manifest:
                raise PackageError('Embedded manifest does not match validated manifest')
        extracted = destination / PREFIX
        if any(not (extracted / name).is_file() for name in required):
            raise PackageError('Extracted package lacks required entrypoint')
        for name in expected:
            if name.endswith('.py'):
                ast.parse((extracted / name).read_text(), filename=name)
        html = (extracted / 'frontend/dist/index.html').read_text()
        assets = re.findall(r'(?:src|href)=["\'](/(?:assets|audio)/[^"\']+)["\']', html)
        if not assets or any(not (extracted / 'frontend/dist' / url.lstrip('/')).is_file() for url in assets):
            raise PackageError('Built frontend assets missing')
        audio_manifest = json.loads((extracted / 'frontend/dist/audio/manifest.json').read_text())
        # The exact source list is also checked via hashes; never execute extracted JS.
        checks['frontend_asset_references'] = assets
        checks['prepared_audio_manifest_present'] = bool(audio_manifest)
        if os.name == 'posix':
            shell_files = [str(extracted / name) for name in expected if name.endswith('.sh')]
            for script in shell_files:
                result = subprocess.run(['bash', '-n', script], capture_output=True, text=True, timeout=10)
                if result.returncode:
                    raise PackageError('Extracted shell syntax failed: ' + Path(script).name)
            checks['shell_syntax'] = True
    return checks


def package(root: Path, output: Path) -> dict:
    root = root.resolve(strict=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path, validation_path = metadata_paths(output)
    if any(os.path.lexists(path) for path in (output, manifest_path, validation_path)):
        raise PackageError('Output archive or sibling metadata already exists; choose a new versioned name')
    files, transformed = collect(root)
    manifest = make_manifest(files, transformed)
    first = zip_bytes(files, manifest)
    second = zip_bytes(files, manifest)
    if first != second:
        raise PackageError('Reproducibility check failed for identical captured inputs')
    checks = validate_archive(first, manifest)
    descriptor, temporary = tempfile.mkstemp(prefix='.source-package-', suffix='.tmp', dir=output.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(first)
        try:
            os.link(temporary, output)
        except FileExistsError as error:
            raise PackageError('Output archive appeared during packaging; refusing overwrite') from error
    finally:
        Path(temporary).unlink(missing_ok=True)
    report = {'archive': output.name, 'sha256': hashlib.sha256(first).hexdigest(), 'archive_bytes': len(first),
              'included_files': len(files) + 1, 'uncompressed_bytes': sum(map(len, files.values())),
              'reproducible_for_same_captured_inputs': True, 'checks': checks,
              'security_screening': {'positive_allowlist': True, 'high_confidence_patterns_passed': True, 'documented_synthetic_fixture_paths': sorted(SYNTHETIC_FIXTURES),
                  'private_path_markdown_transformations': transformed,
                  'limitation': 'Pattern screening is not a proof that all possible secrets or personal data are absent.'},
              'included_paths': sorted([*files, 'PACKAGE-MANIFEST.json'])}
    with manifest_path.open('x') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    with validation_path.open('x') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    return report


def metadata_paths(output: Path) -> tuple[Path, Path]:
    if output.name == 'kontur-dds-source.zip':
        return output.parent/'release-package-manifest.json', output.parent/'release-package-validation.json'
    return output.with_suffix('.manifest.json'), output.with_suffix('.validation.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = package(args.source_root, args.output or args.source_root/'deliverables/kontur-dds-source.zip')
    except (PackageError, OSError, SyntaxError, zipfile.BadZipFile) as error:
        parser.exit(1, f'Packaging failed: {error}\n')
    print(json.dumps({k: report[k] for k in ('archive', 'sha256', 'archive_bytes', 'included_files')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
