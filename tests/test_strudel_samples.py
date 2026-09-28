"""Tests for the Strudel sample installer (task #174).

Network is never touched: _fetch is mocked with a tiny in-memory map of
URLs to bytes.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from miau_dio.strudel import samples


_MANIFEST = json.dumps({
    "_base": "https://example.test/pack/",
    "bd": ["bd/one.wav", "bd/two.wav"],
    "sd": "sd/only.wav",
}).encode()


class _IsolatedCase(unittest.TestCase):
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

    def _fake_fetch(self, url, timeout=60):
        table = {
            "https://example.test/pack.json": _MANIFEST,
            "https://example.test/pack/bd/one.wav": b"wav1",
            "https://example.test/pack/bd/two.wav": b"wav2",
            "https://example.test/pack/sd/only.wav": b"wav3",
        }
        if url not in table:
            raise samples.SampleError(f"no fake for {url}")
        return table[url]


class TestInstall(_IsolatedCase):
    def test_install_writes_files_and_record(self):
        fake_pack = mock.MagicMock()
        fake_pack.name = "testpack"
        fake_pack.manifest_url = "https://example.test/pack.json"
        with mock.patch.object(samples.catalog, "get", return_value=fake_pack):
            with mock.patch.object(samples, "_fetch",
                                   side_effect=self._fake_fetch):
                paths = samples.install("testpack")
        self.assertEqual(len(paths), 4)
        self.assertTrue(samples.is_installed("testpack"))
        self.assertEqual(samples.installed(), ["testpack"])
        # The manifest was fetched and stored under its host/path.
        manifest = samples.cache_dir() / "example.test" / "pack.json"
        self.assertTrue(manifest.is_file())
        # Each wav landed at its mapped path.
        for rel in ["example.test/pack/bd/one.wav",
                    "example.test/pack/bd/two.wav",
                    "example.test/pack/sd/only.wav"]:
            self.assertTrue((samples.cache_dir() / rel).is_file(), rel)

    def test_install_twice_raises(self):
        fake_pack = mock.MagicMock()
        fake_pack.name = "testpack"
        fake_pack.manifest_url = "https://example.test/pack.json"
        with mock.patch.object(samples.catalog, "get", return_value=fake_pack):
            with mock.patch.object(samples, "_fetch",
                                   side_effect=self._fake_fetch):
                samples.install("testpack")
                with self.assertRaises(samples.SampleError):
                    samples.install("testpack")

    def test_install_rolls_back_on_fetch_failure(self):
        fake_pack = mock.MagicMock()
        fake_pack.name = "testpack"
        fake_pack.manifest_url = "https://example.test/pack.json"

        def flaky_fetch(url, timeout=60):
            if url.endswith("two.wav"):
                raise samples.SampleError("boom")
            return self._fake_fetch(url)

        with mock.patch.object(samples.catalog, "get", return_value=fake_pack):
            with mock.patch.object(samples, "_fetch", side_effect=flaky_fetch):
                with self.assertRaises(samples.SampleError):
                    samples.install("testpack")
        # Record must not exist and files must be cleaned up.
        self.assertFalse(samples.is_installed("testpack"))
        self.assertFalse((samples.cache_dir() / "example.test"
                          / "pack" / "bd" / "one.wav").exists())


class TestRemove(_IsolatedCase):
    def test_remove_deletes_files(self):
        fake_pack = mock.MagicMock()
        fake_pack.name = "testpack"
        fake_pack.manifest_url = "https://example.test/pack.json"
        with mock.patch.object(samples.catalog, "get", return_value=fake_pack):
            with mock.patch.object(samples, "_fetch",
                                   side_effect=self._fake_fetch):
                samples.install("testpack")
        n = samples.remove("testpack")
        self.assertEqual(n, 4)
        self.assertFalse(samples.is_installed("testpack"))
        # The pack's subtree is pruned.
        self.assertFalse((samples.cache_dir() / "example.test").exists())

    def test_remove_missing_raises(self):
        with self.assertRaises(samples.SampleError):
            samples.remove("nothing")


class TestSizeOnDisk(_IsolatedCase):
    def test_zero_when_missing(self):
        self.assertEqual(samples.size_on_disk("nothing"), 0)

    def test_counts_all_files(self):
        fake_pack = mock.MagicMock()
        fake_pack.name = "testpack"
        fake_pack.manifest_url = "https://example.test/pack.json"
        with mock.patch.object(samples.catalog, "get", return_value=fake_pack):
            with mock.patch.object(samples, "_fetch",
                                   side_effect=self._fake_fetch):
                samples.install("testpack")
        # 4 fake files: manifest (28) + wav1 (4) + wav2 (4) + wav3 (4).
        self.assertEqual(samples.size_on_disk("testpack"),
                         len(_MANIFEST) + 4 + 4 + 4)


if __name__ == "__main__":
    unittest.main()
