import json
from pathlib import Path
import tempfile
import unittest

from build_indexes import build_indexes


class FilenameTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'parts' / 'Nested Folder').mkdir(parents=True)
        (self.root / 'schemes').mkdir()
        (self.root / 'index.json').write_text(json.dumps({
            'partsDir': 'parts', 'schemesDir': 'schemes',
            'partsIndex': 'parts-index.json', 'schemesIndex': 'schemes-index.json',
        }))
        (self.root / 'parts-index.json').write_text('[]')
        (self.root / 'schemes-index.json').write_text('[]')
        self.part = self.root / 'parts' / 'Nested Folder' / 'My Pickup.part.JSON'
        self.part.write_bytes(b'{"name": "Keep My Name"}')
        self.scheme = self.root / 'schemes' / 'My Scheme.scheme.json'
        self.scheme.write_text(json.dumps({
            'name': 'My Scheme', 'description': 'Keep Description', 'tags': {'$values': ['Tag']},
        }))

    def test_rename_and_indexes_are_consistent_and_repeatable(self):
        original_part = self.part.read_bytes()
        original_scheme = self.scheme.read_bytes()
        self.assertEqual(build_indexes(self.root), {'parts': 1, 'schemes': 1})
        part = self.part.with_name('my-pickup.part.json')
        scheme = self.scheme.with_name('my-scheme.scheme.json')
        self.assertEqual(part.read_bytes(), original_part)
        self.assertEqual(scheme.read_bytes(), original_scheme)
        self.assertFalse(self.part.exists())
        self.assertFalse(self.scheme.exists())
        self.assertEqual(json.loads((self.root / 'parts-index.json').read_text()),
                         ['Nested Folder/my-pickup.part.json'])
        self.assertEqual(json.loads((self.root / 'schemes-index.json').read_text()), [{
            'file': 'my-scheme.scheme.json', 'name': 'My Scheme',
            'description': 'Keep Description', 'tags': ['Tag'],
        }])
        before = self.snapshot()
        build_indexes(self.root)
        self.assertEqual(self.snapshot(), before)

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def test_collisions_preserve_all_files_and_indexes(self):
        for name in ('my-pickup.part.json', 'MY-PICKUP.part.JSON'):
            with self.subTest(name=name):
                collision = self.part.with_name(name)
                collision.write_text('{"different": true}')
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'collision|already exists'):
                    build_indexes(self.root)
                self.assertEqual(self.snapshot(), before)
                collision.unlink()

    def test_invalid_metadata_prevents_renames(self):
        self.scheme.write_text('{}')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            build_indexes(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_circuit_export_metadata_is_indexed_without_changing_contents(self):
        for tags in ([], ['single coil'], {'$id': '3', '$values': ['single coil']}):
            with self.subTest(tags=tags):
                self.scheme = self.root / 'schemes' / 'My Scheme.scheme.json'
                self.scheme.write_text(json.dumps({
                    '$id': '1', 'schemeFormatVersion': 1,
                    'circuit': {'$id': '2', 'name': 'Simple sss', 'description': '', 'tags': tags},
                }))
                original = self.scheme.read_bytes()
                build_indexes(self.root)
                normalized = self.scheme.with_name('my-scheme.scheme.json')
                self.assertEqual(normalized.read_bytes(), original)
                self.assertEqual(json.loads((self.root / 'schemes-index.json').read_text()), [{
                    'file': 'my-scheme.scheme.json', 'name': 'Simple sss',
                    'description': '', 'tags': tags if isinstance(tags, list) else tags['$values'],
                }])
                normalized.unlink()

    def test_invalid_circuit_metadata_preserves_files_and_indexes(self):
        for circuit in (None, [], {}, {'name': 123, 'description': '', 'tags': []},
                        {'name': 'Test', 'description': None, 'tags': []},
                        {'name': 'Test', 'description': '', 'tags': [123]}):
            with self.subTest(circuit=circuit):
                self.scheme.write_text(json.dumps({'circuit': circuit}))
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, 'circuit'):
                    build_indexes(self.root)
                self.assertEqual(self.snapshot(), before)

    def test_index_preserves_exact_scheme_attributes_for_multiple_files(self):
        metadata = {
            'name': '  Čistý SSS – Volume & Tone  ',
            'description': 'Prvý riadok.\n  Druhý riadok s medzerami.  ',
            'tags': ['Single Coil', ' SSS ', 'single coil', 'Single Coil'],
        }
        self.scheme.write_text(json.dumps({
            'name': 'Do not use root metadata', 'description': 'Wrong description',
            'tags': ['wrong'], 'schemeFormatVersion': 1,
            'circuit': {**metadata, 'tags': {'$values': metadata['tags']},
                        'parts': {'$values': [{'name': 'Pickup', 'tags': ['wrong part tag']}]}},
        }, ensure_ascii=False))
        nested = self.root / 'schemes' / 'Nested'
        nested.mkdir()
        empty = nested / 'Empty Scheme.scheme.json'
        empty.write_text(json.dumps({
            'circuit': {'name': '', 'description': '', 'tags': []},
        }))
        originals = {self.scheme: self.scheme.read_bytes(), empty: empty.read_bytes()}

        self.assertEqual(build_indexes(self.root), {'parts': 1, 'schemes': 2})
        entries = json.loads((self.root / 'schemes-index.json').read_text())
        self.assertEqual(entries, [
            {'file': 'Nested/empty-scheme.scheme.json', 'name': '', 'description': '', 'tags': []},
            {'file': 'my-scheme.scheme.json', **metadata},
        ])
        for original, content in originals.items():
            self.assertEqual(original.with_name(original.name.lower().replace(' ', '-')).read_bytes(), content)
