"""Tests for the local Strudel server (task #174) -- stdlib unittest only."""
import json
import os
import pathlib
import tempfile
import unittest
import urllib.request

from miau_dio.strudel import StrudelError, samples_dir, serve_background


class _IsolatedCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = self._tmp.name
        self.srv, self.url, self._th = serve_background(port=0)
        self.addCleanup(self.srv.shutdown)
        self.addCleanup(self.srv.server_close)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = self._prev
        self._tmp.cleanup()

    def _get(self, path: str):
        with urllib.request.urlopen(self.url + path.lstrip("/")) as r:
            return r.status, r.read()


class TestServe(_IsolatedCase):
    def test_index_served(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        # The vendored site is the official one; its title is "Strudel REPL".
        self.assertIn(b"<title>Strudel REPL</title>", body)

    def test_index_injects_fetch_shim(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"NATIVE_FETCH", body)
        self.assertIn(b"SHIM_HOSTS", body)
        self.assertIn(b"raw.githubusercontent.com", body)

    def test_site_asset_served(self):
        status, body = self._get("/_astro/Repl.tMWe_n7b.js")
        self.assertEqual(status, 200)
        self.assertGreater(len(body), 1000)

    def test_missing_asset_404(self):
        try:
            self._get("/_astro/nope.js")
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_path_traversal_rejected(self):
        try:
            self._get("/_astro/../etc/passwd")
            self.fail("expected HTTPError")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (400, 404))


class TestSamples(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = self._tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = self._prev
        self._tmp.cleanup()

    def test_dir_created_on_access(self):
        d = samples_dir()
        self.assertTrue(d.is_dir())

    def test_samples_listed_via_json_endpoint(self):
        d = samples_dir()
        (d / "kick.wav").write_bytes(b"RIFF")
        srv, url, _ = serve_background(port=0)
        try:
            with urllib.request.urlopen(url + "samples/index.json") as r:
                body = json.loads(r.read())
            self.assertEqual(body, {"kick": "/samples/kick.wav"})
        finally:
            srv.shutdown()
            srv.server_close()

    def test_sample_served(self):
        d = samples_dir()
        payload = b"RIFFfakewavdata"
        (d / "snare.wav").write_bytes(payload)
        srv, url, _ = serve_background(port=0)
        try:
            with urllib.request.urlopen(url + "samples/snare.wav") as r:
                self.assertEqual(r.read(), payload)
        finally:
            srv.shutdown()
            srv.server_close()


class TestErrors(unittest.TestCase):
    def test_missing_site_raises(self):
        from miau_dio.strudel import server as srvmod
        old = srvmod._SITE
        srvmod._SITE = pathlib.Path("/nonexistent/site")
        try:
            with self.assertRaises(StrudelError):
                srvmod.serve()
        finally:
            srvmod._SITE = old


if __name__ == "__main__":
    unittest.main()
