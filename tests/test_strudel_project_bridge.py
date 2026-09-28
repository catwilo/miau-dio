"""Tests for /project/* endpoints on the Strudel server (task #174)."""
import json
import pathlib
import tempfile
import unittest
import urllib.request
import urllib.error

from miau_dio.strudel import StrudelError, serve_background


class _ProjectCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.proj = self.root / "demo"
        (self.proj / "patterns").mkdir(parents=True)
        (self.proj / "project.json").write_text(
            json.dumps({"name": "demo", "tracks": []})
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _serve(self, project_dir=None):
        srv, url, _ = serve_background(port=0, project_dir=project_dir)
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)
        return url


class TestProjectInfo(_ProjectCase):
    def test_info_without_project_404(self):
        url = self._serve(project_dir=None)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(url + "project/info")
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()

    def test_info_with_project(self):
        url = self._serve(project_dir=self.proj)
        with urllib.request.urlopen(url + "project/info") as r:
            data = json.loads(r.read())
        self.assertEqual(data["name"], "demo")
        self.assertEqual(data["patterns"], [])

    def test_invalid_project_dir_rejected(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(StrudelError):
            serve_background(port=0, project_dir=empty)


class TestPatternCRUD(_ProjectCase):
    def test_save_and_read(self):
        url = self._serve(project_dir=self.proj)
        body = b's("bd sd")'
        req = urllib.request.Request(
            url + "project/pattern/foo", data=body, method="POST"
        )
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read())
        self.assertEqual(result["saved"], "foo.js")
        self.assertEqual(result["bytes"], len(body))
        with urllib.request.urlopen(url + "project/pattern/foo.js") as r:
            self.assertEqual(r.read(), body)

    def test_save_without_project_404(self):
        url = self._serve(project_dir=None)
        req = urllib.request.Request(
            url + "project/pattern/foo", data=b"x", method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()

    def test_missing_pattern_404(self):
        url = self._serve(project_dir=self.proj)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(url + "project/pattern/nope.js")
        self.assertEqual(cm.exception.code, 404)
        cm.exception.close()

    def test_traversal_rejected_get(self):
        url = self._serve(project_dir=self.proj)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(
                url + "project/pattern/..%2F..%2Fetc%2Fpasswd"
            )
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_traversal_rejected_post(self):
        url = self._serve(project_dir=self.proj)
        req = urllib.request.Request(
            url + "project/pattern/..%2F..%2Fetc%2Fpasswd",
            data=b"x", method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_hidden_name_rejected(self):
        url = self._serve(project_dir=self.proj)
        req = urllib.request.Request(
            url + "project/pattern/.secret", data=b"x", method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_payload_too_large_rejected(self):
        from miau_dio.strudel import server as srvmod
        url = self._serve(project_dir=self.proj)
        # One byte over the cap.
        big = b"x" * (srvmod.MAX_PATTERN_BYTES + 1)
        req = urllib.request.Request(
            url + "project/pattern/huge", data=big, method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 413)
        cm.exception.close()

    def test_info_lists_saved_patterns(self):
        url = self._serve(project_dir=self.proj)
        for name in ("a", "b"):
            req = urllib.request.Request(
                url + "project/pattern/" + name, data=b"x", method="POST"
            )
            urllib.request.urlopen(req).read()
        with urllib.request.urlopen(url + "project/info") as r:
            data = json.loads(r.read())
        self.assertEqual(data["patterns"], ["a.js", "b.js"])


if __name__ == "__main__":
    unittest.main()
