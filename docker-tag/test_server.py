import json
from pathlib import Path
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import make_server


class TagServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "tags.json"
        self.original = b'[ " Switch ", "PICKUP", "switch" ]\n'
        self.path.write_bytes(self.original)
        self.backup = self.path.with_name("tags.json.bak")
        self.server = make_server(self.path, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.directory.cleanup()

    def request(self, path="/api/tags", data=None, headers=None):
        request = Request(self.url + path,
                          data=None if data is None else json.dumps(data).encode(),
                          headers=headers or {"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=3)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            return response.status, json.loads(raw) if response.headers.get_content_type() == "application/json" else raw

    def test_load_normalizes_without_writing(self):
        status, data = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(data["tags"], ["switch", "pickup"])
        self.assertTrue(data["normalized"])
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.backup.exists())

    def test_add_edit_delete_save_and_reload(self):
        _, loaded = self.request()
        # Add a tag, edit the first, delete the second, and save the resulting list.
        tags = loaded["tags"] + [" Humbucker "]
        tags[0] = " Toggle Switch "
        del tags[1]
        status, saved = self.request(data={"tags": tags, "revision": loaded["revision"]})
        self.assertEqual(status, 200)
        self.assertEqual(saved["tags"], ["humbucker", "toggle switch"])
        self.assertEqual(json.loads(self.path.read_bytes()), saved["tags"])
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.request()[1]["tags"], saved["tags"])
        self.assertEqual(self.request(data={"tags": [], "revision": saved["revision"]})[0], 200)
        self.assertEqual(json.loads(self.path.read_bytes()), [])
        self.assertFalse(self.backup.exists())

    def test_invalid_edits_do_not_touch_files(self):
        _, loaded = self.request()
        for tags in (["Switch", " switch "], [" "], [12], {"tags": []}, None):
            with self.subTest(tags=tags):
                status, _ = self.request(data={"tags": tags, "revision": loaded["revision"]})
                self.assertEqual(status, 400)
                self.assertEqual(self.path.read_bytes(), self.original)
                self.assertFalse(self.backup.exists())

    def test_stale_revision_preserves_external_change(self):
        _, loaded = self.request()
        external = b'["external"]'
        self.path.write_bytes(external)
        status, _ = self.request(data={"tags": ["new"], "revision": loaded["revision"]})
        self.assertEqual(status, 409)
        self.assertEqual(self.path.read_bytes(), external)
        self.assertFalse(self.backup.exists())

    def test_bad_source_is_never_overwritten(self):
        for raw in (b'{"tags": ["switch"]}', b'not json', b'[" "]', b'[2]'):
            with self.subTest(raw=raw):
                self.path.write_bytes(raw)
                self.assertEqual(self.request()[0], 422)
                self.assertEqual(self.request(data={"tags": [], "revision": "x"})[0], 400)
                self.assertEqual(self.path.read_bytes(), raw)
                self.assertFalse(self.backup.exists())

    def test_write_failure_preserves_original(self):
        _, loaded = self.request()
        with patch("server.atomic_write", side_effect=OSError("permission denied")):
            status, _ = self.request(data={"tags": ["new"], "revision": loaded["revision"]})
        self.assertEqual(status, 500)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_static_files_and_restricted_routes(self):
        for route in ("/", "/app.js", "/style.css"):
            self.assertEqual(self.request(path=route)[0], 200)
        for route in ("/server.py", "/tags.json", "/../tags.json"):
            self.assertEqual(self.request(path=route)[0], 404)

    def test_foreign_origin_and_non_json_rejected(self):
        data = {"tags": [], "revision": "x"}
        for route in ("/api/tags", "/api/indexes"):
            self.assertEqual(self.request(path=route, data=data, headers={"Content-Type": "application/json", "Origin": "https://example.org"})[0], 403)
            self.assertEqual(self.request(path=route, data=data, headers={"Content-Type": "text/plain"})[0], 415)

    def catalog(self):
        root = self.path.parent
        config = {"partsDir": "https://example.org/catalog/parts/", "schemesDir": "schemes",
                  "partsIndex": "parts-index.json", "schemesIndex": "schemes-index.json"}
        (root / "index.json").write_text(json.dumps(config))
        (root / "parts" / "nested").mkdir(parents=True)
        (root / "schemes").mkdir()
        (root / "parts" / "z.json").write_text('{}')
        (root / "parts" / "nested" / "a.json").write_text('{}')
        (root / "schemes" / "one.json").write_text(json.dumps({
            "name": "Example", "description": "Test scheme", "tags": {"$values": ["pickup"]}}))
        (root / "parts-index.json").write_text('["stale.json"]')
        (root / "schemes-index.json").write_text('[]')
        return root, config

    def test_rebuild_indexes_from_local_catalog(self):
        root, _ = self.catalog()
        status, data = self.request(path="/api/indexes", data={})
        self.assertEqual(status, 200)
        self.assertEqual(data, {"parts": 2, "schemes": 1})
        self.assertEqual(json.loads((root / "parts-index.json").read_text()), ['nested/a.json', 'z.json'])
        self.assertEqual(json.loads((root / "schemes-index.json").read_text()), [{
            "file": "one.json", "name": "Example", "description": "Test scheme", "tags": ["pickup"]}])
        self.assertEqual(self.path.read_bytes(), self.original)
        # Removing source files also removes their entries on the next rebuild.
        (root / "parts" / "z.json").unlink()
        (root / "schemes" / "one.json").unlink()
        self.assertEqual(self.request(path="/api/indexes", data={})[1], {"parts": 1, "schemes": 0})

    def test_invalid_scheme_preserves_both_indexes_and_allows_retry(self):
        root, _ = self.catalog()
        scheme = root / "schemes" / "one.json"
        scheme.write_text('{"name": "Invalid"}')
        status, data = self.request(path="/api/indexes", data={})
        self.assertEqual(status, 422)
        self.assertIn("description", data["error"])
        self.assertEqual((root / "parts-index.json").read_text(), '["stale.json"]')
        self.assertEqual((root / "schemes-index.json").read_text(), '[]')
        scheme.write_text('{"name": "Valid", "description": "", "tags": []}')
        self.assertEqual(self.request(path="/api/indexes", data={})[0], 200)

    def test_invalid_index_paths_are_rejected(self):
        root, config = self.catalog()
        for destination in ('../outside.json', 'schemes-index.json'):
            config['partsIndex'] = destination
            (root / "index.json").write_text(json.dumps(config))
            self.assertEqual(self.request(path="/api/indexes", data={})[0], 422)
            self.assertEqual((root / "parts-index.json").read_text(), '["stale.json"]')

    def test_index_write_error_is_reported(self):
        with patch("server.build_indexes", side_effect=OSError("permission denied")):
            status, data = self.request(path="/api/indexes", data={})
        self.assertEqual(status, 500)
        self.assertIn("permission denied", data["error"])

    def test_concurrent_rebuild_is_rejected(self):
        started, release = threading.Event(), threading.Event()

        def build(_):
            started.set()
            release.wait(timeout=2)
            return {"parts": 0, "schemes": 0}

        with patch("server.build_indexes", side_effect=build), ThreadPoolExecutor() as pool:
            first = pool.submit(self.request, path="/api/indexes", data={})
            try:
                self.assertTrue(started.wait(timeout=1))
                self.assertEqual(self.request(path="/api/indexes", data={})[0], 409)
            finally:
                release.set()
            self.assertEqual(first.result()[0], 200)

    def test_rebuild_request_cannot_override_catalog_root(self):
        self.assertEqual(self.request(path="/api/indexes", data={"root": "/tmp"})[0], 400)


if __name__ == "__main__":
    unittest.main()
