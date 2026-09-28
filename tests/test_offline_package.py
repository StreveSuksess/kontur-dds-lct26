"""Narrow adversarial checks of packaging; no real archive/runtime mutated."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import package_offline as package


class OfflinePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root/'bundle'
        self.bundle.mkdir()
        self.files = {'requirements.txt': b'fastapi==0.1\n', 'wheels/synthetic-0.1-py3-none-any.whl': b'synthetic fixture, never installed', 'frontend-dist/index.html': b'<html>snapshot</html>'}
        self.source = {'backend/uv.lock':b'lock', 'backend/pyproject.toml':b'project', 'frontend/dist/index.html':self.files['frontend-dist/index.html'], 'scripts/start.sh':b'#!/bin/sh\nexit 0\n'}
        self.manifest = {'format':'dds-offline-v1','target':{'major_minor':[3,12],'implementation':'CPython','system':'Darwin','machine':'arm64'}, 'files':{name:hashlib.sha256(data).hexdigest() for name,data in self.files.items()},'wheel_count':1, 'uv_lock_sha256':package.digest(b'lock'), 'pyproject_sha256':package.digest(b'project')}
        for name,data in self.files.items():
            path = self.bundle/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.write_manifest()

    def write_manifest(self):
        (self.bundle/'manifest.json').write_text(json.dumps(self.manifest))

    def pack(self, output):
        with patch.object(package, 'load_source', return_value=(dict(self.source),'source-fixture-sha256')):
            return package.package(self.root/'source.zip', self.bundle, output)

    def test_corrupted_or_extra_wheelhouse_file_rejected(self):
        (self.bundle/'requirements.txt').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):
            package.load_bundle(self.bundle)
        (self.bundle/'requirements.txt').write_bytes(self.files['requirements.txt'])
        (self.bundle/'private.db').write_bytes(b'not allowed')
        with self.assertRaisesRegex(ValueError,'unmanifested'):
            package.load_bundle(self.bundle)

    def test_symlink_and_traversal_rejected(self):
        target = self.bundle/'requirements.txt'
        target.unlink()
        other = self.root/'requirements-copy.txt'
        other.write_bytes(self.files['requirements.txt'])
        target.symlink_to(other)
        with self.assertRaisesRegex(ValueError,'Symlink'):
            package.load_bundle(self.bundle)
        target.unlink()
        target.write_bytes(self.files['requirements.txt'])
        self.manifest['files']['../outside.txt'] = 'x'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError,'Unsafe path'):
            package.load_bundle(self.bundle)

    def test_source_zip_traversal_and_symlink_rejected_before_extraction(self):
        source = self.root/'unsafe.zip'
        with zipfile.ZipFile(source, 'w') as archive:
            archive.writestr('kontur-dds/../outside', b'unsafe')
        with self.assertRaisesRegex(ValueError,'Unsafe path'):
            package.load_source(source)
        with zipfile.ZipFile(source, 'w') as archive:
            info = zipfile.ZipInfo('kontur-dds/link')
            info.external_attr = 0o120777 << 16
            archive.writestr(info,b'elsewhere')
        with self.assertRaisesRegex(ValueError,'Non-regular'):
            package.load_source(source)
        self.assertFalse((self.root/'outside').exists())

    def test_frontend_and_dependency_mismatch_refuse_publication(self):
        output = self.root/'output.zip'
        self.source['frontend/dist/index.html'] = b'new version'
        with self.assertRaisesRegex(ValueError,'frontend differs'):
            self.pack(output)
        self.assertFalse(output.exists())
        self.source['frontend/dist/index.html'] = self.files['frontend-dist/index.html']
        self.source['backend/uv.lock'] = b'new dependencies'
        with self.assertRaisesRegex(ValueError,'dependencies differ'):
            self.pack(output)
        self.assertFalse(output.exists())

    def test_package_is_deterministic_and_never_overwrites(self):
        first, second = self.root/'one.zip', self.root/'two.zip'
        report = self.pack(first)
        self.pack(second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertTrue(report['checks']['same_inputs_deterministic'])
        with zipfile.ZipFile(first) as archive:
            names = archive.namelist()
            self.assertIn('kontur-dds/runtime/offline-wheelhouse/requirements.txt',names)
            self.assertIn('kontur-dds/OFFLINE-INSTALL-README.md',names)
            manifest = json.loads(archive.read('kontur-dds/OFFLINE-PACKAGE-MANIFEST.json'))
            for entry in manifest['entries']:
                self.assertEqual(package.digest(archive.read('kontur-dds/'+entry['path'])),entry['sha256'])
        before = first.read_bytes()
        with self.assertRaisesRegex(ValueError,'already exists'):
            self.pack(first)
        with self.assertRaises(FileExistsError):
            package.publish_new(first,b'overwrite attempt')
        self.assertEqual(first.read_bytes(), before)

    def test_refresh_copies_new_frontend_without_changing_original(self):
        project = self.root/'project'
        for name,data in self.source.items():
            path = project/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (project/'frontend/dist/index.html').write_bytes(b'<html>frozen release</html>')
        destination = self.root/'release'
        result = package.refresh_bundle(self.bundle, destination, project)
        self.assertFalse(result['network_used'])
        self.assertEqual((destination/'frontend-dist/index.html').read_bytes(),b'<html>frozen release</html>')
        self.assertEqual((self.bundle/'frontend-dist/index.html').read_bytes(),self.files['frontend-dist/index.html'])
        package.load_bundle(destination)
        with self.assertRaisesRegex(ValueError,'already exists'):
            package.refresh_bundle(self.bundle, destination, project)


if __name__ == '__main__':
    unittest.main()
