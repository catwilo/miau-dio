"""Tests for the Strudel sample installer (task #174).

Network is never touched: _fetch is mocked with a tiny in-memory map of
URLs to bytes.
"""
import json
import os
import pathlib
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


class TestVendored(_IsolatedCase):
    """The vendor/ tree ships packs inside the repo, no network, no cache."""

    def _fake_vendor(self, name="vpack", files=None):
        if files is None:
            files = {"vpack.json": b"{}",
                     "bd/one.wav": b"wavA",
                     "sd/two.wav": b"wavB"}
        root = pathlib.Path(self._tmp.name) / "vendor" / name
        for rel, body in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(body)
        return root

    def test_vendored_lists_pack_with_manifest(self):
        self._fake_vendor("vpack")
        root = pathlib.Path(self._tmp.name) / "vendor"
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            self.assertEqual(samples.vendored(), ["vpack"])

    def test_vendored_ignores_dir_without_json(self):
        root = pathlib.Path(self._tmp.name) / "vendor"
        (root / "nomanifest").mkdir(parents=True)
        (root / "nomanifest" / "x.wav").write_bytes(b"x")
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            self.assertEqual(samples.vendored(), [])

    def test_available_unions_cache_and_vendor(self):
        root = pathlib.Path(self._tmp.name) / "vendor"
        (root / "vpack").mkdir(parents=True)
        (root / "vpack" / "v.json").write_bytes(b"{}")
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            self.assertEqual(samples.available(), ["vpack"])

    def test_is_installed_is_cache_only(self):
        root = pathlib.Path(self._tmp.name) / "vendor"
        (root / "vpack").mkdir(parents=True)
        (root / "vpack" / "v.json").write_bytes(b"{}")
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            self.assertFalse(samples.is_installed("vpack"))
            self.assertEqual(samples.installed(), [])

    def test_install_vendored_raises(self):
        root = pathlib.Path(self._tmp.name) / "vendor"
        (root / "vpack").mkdir(parents=True)
        (root / "vpack" / "v.json").write_bytes(b"{}")
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            with self.assertRaises(samples.SampleError):
                samples.install("vpack")

    def test_remove_vendored_raises(self):
        root = pathlib.Path(self._tmp.name) / "vendor"
        (root / "vpack").mkdir(parents=True)
        (root / "vpack" / "v.json").write_bytes(b"{}")
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            with self.assertRaises(samples.SampleError):
                samples.remove("vpack")

    def test_size_on_disk_vendored(self):
        self._fake_vendor("vpack", files={
            "vpack.json": b"{}", "bd/a.wav": b"1234", "sd/b.wav": b"5678"})
        root = pathlib.Path(self._tmp.name) / "vendor"
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            self.assertEqual(samples.size_on_disk("vpack"), 2 + 4 + 4)

    def test_preview_vendored_reads_repo_files(self):
        self._fake_vendor("vpack")
        root = pathlib.Path(self._tmp.name) / "vendor"
        fake_pack = mock.MagicMock()
        fake_pack.name = "vpack"
        fake_pack.manifest_url = "https://example.test/vpack.json"
        with mock.patch.object(samples, "_vendor_root", return_value=root):
            with mock.patch.object(samples.catalog, "get",
                                   return_value=fake_pack):
                with mock.patch.object(samples, "_fetch") as fetch_mock:
                    items = samples.preview("vpack")
        fetch_mock.assert_not_called()
        labels = sorted(label for label, _ in items)
        self.assertEqual(labels, ["bd/one.wav", "sd/two.wav"])
        for _, p in items:
            self.assertTrue(p.is_file())


class TestRealVendorTree(unittest.TestCase):
    """Pin the packs actually shipped with the repo."""

    def test_uzu_and_dirt_are_vendored(self):
        self.assertIn("uzu", samples.vendored())
        self.assertIn("dirt", samples.vendored())

    def test_uzu_manifest_present(self):
        root = samples._vendor_root() / "uzu"
        self.assertTrue((root / "strudel.json").is_file())
        self.assertTrue((root / "bd" / "10_bd_switchangel.wav").is_file())

    def test_dirt_manifest_present(self):
        root = samples._vendor_root() / "dirt"
        self.assertTrue((root / "Dirt-Samples.json").is_file())
        self.assertTrue((root / "casio" / "high.wav").is_file())

    def test_guitar_vendored(self):
        self.assertIn("guitar", samples.vendored())
        root = samples._vendor_root() / "guitar"
        self.assertTrue((root / "guitar.json").is_file())
        self.assertTrue((root / "A2.wav").is_file())

    def test_guitar_manifest_maps_sharps(self):
        import json as _json
        manifest = _json.loads(
            (samples._vendor_root() / "guitar" / "guitar.json").read_text())
        notes = manifest["guitar"]
        self.assertIn("A2", notes)
        self.assertIn("A#2", notes)  # converted from tonejs' As2
        self.assertEqual(notes["A#2"], "As2.wav")

    def test_trumpet_vendored(self):
        self.assertIn("trumpet", samples.vendored())
        root = samples._vendor_root() / "trumpet"
        self.assertTrue((root / "trumpet.json").is_file())

    def test_trumpet_manifest_maps_sharp_url_encoded(self):
        import json as _json
        manifest = _json.loads(
            (samples._vendor_root() / "trumpet" / "trumpet.json").read_text())
        notes = manifest["trumpet"]
        self.assertIn("A#3", notes)
        self.assertTrue(all("%23" in f or "#" not in f for f in notes["A#3"]))
        disk = samples._vendor_root() / "trumpet"
        for f in notes["A#3"]:
            self.assertTrue((disk / f).is_file(), f)

    def test_trumpet_stac_vendored(self):
        self.assertIn("trumpet_stac", samples.vendored())
        root = samples._vendor_root() / "trumpet_stac"
        self.assertTrue((root / "trumpet_stac.json").is_file())

    def test_trombone_vendored(self):
        self.assertIn("trombone", samples.vendored())
        root = samples._vendor_root() / "trombone"
        self.assertTrue((root / "trombone.json").is_file())

    def test_trombone_stac_vendored(self):
        self.assertIn("trombone_stac", samples.vendored())
        root = samples._vendor_root() / "trombone_stac"
        self.assertTrue((root / "trombone_stac.json").is_file())

    def test_trombone_manifest_url_encoded_base(self):
        import json as _json
        manifest = _json.loads(
            (samples._vendor_root() / "trombone" / "trombone.json").read_text())
        self.assertIn("Tenor%20Trombone", manifest["_base"])
        for files in manifest["trombone"].values():
            for f in files:
                self.assertNotIn(" ", f, "manifest value must not have raw space")
                self.assertNotIn("#", f, "manifest value must use %23")


if __name__ == "__main__":
    unittest.main()
