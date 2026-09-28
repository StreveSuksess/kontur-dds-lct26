"""Archive security and reproducibility checks; no external dependencies."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

MODULE_PATH = Path(__file__).resolve().parents[1] / 'scripts/package_release.py'
spec = importlib.util.spec_from_file_location('package_release', MODULE_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReleasePackageTests(unittest.TestCase):
    def test_package_refuses_existing_archive_or_sibling_metadata_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root/'kontur-dds-source-rc2.zip'
            manifest, validation = m.metadata_paths(output)
            for occupied in (output, manifest, validation):
                occupied.write_text('frozen')
                with self.subTest(occupied=occupied.name), patch.object(m, 'collect', side_effect=AssertionError('must not collect')):
                    with self.assertRaisesRegex(m.PackageError, 'already exists'):
                        m.package(root, output)
                self.assertEqual(occupied.read_text(), 'frozen')
                occupied.unlink()

    def test_versioned_package_keeps_frozen_rc1_metadata_paths(self):
        root = Path('/tmp/kontur-release-test')
        self.assertEqual(m.metadata_paths(root/'kontur-dds-source.zip'),
                         (root/'release-package-manifest.json', root/'release-package-validation.json'))
        self.assertEqual(m.metadata_paths(root/'kontur-dds-source-rc2.zip'),
                         (root/'kontur-dds-source-rc2.manifest.json', root/'kontur-dds-source-rc2.validation.json'))

    def test_paths_reject_traversal_absolute_and_alternate_separators(self):
        for path in ('../secret', '/etc/passwd', 'a/../b', 'a\\b', 'C:/x', 'a//b', 'a/./b'):
            with self.subTest(path=path), self.assertRaises(m.PackageError):
                m.safe_path(path)

    def test_selection_rejects_runtime_env_database_and_private_manifest(self):
        for path in ('backend/var/dds.db', 'backend/.env', '.env', 'frontend/node_modules/a.js',
                     'research/source-manifest.json', 'research/qa-session.mp4', 'models/model.gguf',
                     'runtime/secret.py', 'docs/password.pem', 'deliverables/previous.zip',
                     'frontend/src/cache.pyc', 'docs/pilot-templates/private-key.txt',
                     'docs/specs/unreviewed.md', 'research/source-manifest.json',
                     'research/model-comparison/results.partial.json',
                     'research/model-comparison/server.json'):
            with self.subTest(path=path):
                self.assertFalse(m.selected(path))
        for path in ('backend/app/main.py', 'frontend/dist/index.html', 'frontend/dist/assets/main.js',
                     'docs/release-package.md', '.env.example', 'docs/specs/criterion-review.md',
                     'docs/pilot-templates/adjudication.csv', 'tests/report_state.test.mjs',
                     'research/model-comparison/preregistration.json',
                     'research/model-comparison/holdout.json'):
            self.assertTrue(m.selected(path))

    def test_secret_error_does_not_echo_key_and_exception_is_exact(self):
        key = ('sk-' + 'A' * 48).encode()
        with self.assertRaises(m.PackageError) as caught:
            m.security_scan('docs/example.json', key)
        self.assertNotIn(key.decode(), str(caught.exception))
        synthetic = b'http://user:' + b'secret@localhost:80'
        m.security_scan('backend/tests/test_ai.py', synthetic)
        with self.assertRaises(m.PackageError):
            m.security_scan('docs/example.md', synthetic)
        with self.assertRaises(m.PackageError):
            m.security_scan('backend/tests/test_ai.py', b'https://real:' + b'credential@service.test')

    def test_pptx_embedded_xml_is_scanned(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('ppt/slides/slide1.xml', 'sk-' + 'B' * 48)
        with self.assertRaises(m.PackageError):
            m.security_scan('deliverables/example.pptx', stream.getvalue())

    def test_collector_rejects_selected_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root/'outside.txt').write_text('value')
            (root/'README.md').symlink_to(root/'outside.txt')
            with patch.object(m, 'REQUIRED', set()), self.assertRaises(m.PackageError):
                m.collect(root)

    def test_markdown_sanitization_is_declared_and_original_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            original = 'Location: ' + str(root) + '/docs'
            (root/'README.md').write_text(original)
            with patch.object(m, 'REQUIRED', set()):
                files, changes = m.collect(root)
            self.assertEqual(files['README.md'], b'Location: ./docs')
            self.assertEqual((root/'README.md').read_text(), original)
            self.assertEqual(changes[0]['source_sha256'], hashlib.sha256(original.encode()).hexdigest())

    def test_zip_order_timestamp_modes_and_bytes_are_deterministic(self):
        files = {'docs/a.md': b'text', 'scripts/start.sh': b'#!/bin/sh\nexit 0\n'}
        manifest = m.make_manifest(files, [])
        first = m.zip_bytes(files, manifest)
        second = m.zip_bytes(dict(reversed(list(files.items()))), manifest)
        self.assertEqual(first, second)
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            for info in archive.infolist():
                self.assertEqual(info.date_time, m.FIXED_TIME)
            self.assertEqual((archive.getinfo('kontur-dds/scripts/start.sh').external_attr >> 16) & 0o777, 0o755)
            self.assertEqual(json.loads(archive.read('kontur-dds/PACKAGE-MANIFEST.json')), manifest)


if __name__ == '__main__':
    unittest.main()
