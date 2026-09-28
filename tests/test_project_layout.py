"""Tests for the Project directory layout (task #172) -- stdlib unittest."""
import json
import os
import pathlib
import tempfile
import unittest

from miau_dio.project import layout
from miau_dio.project.model import Project, Track


class _IsolatedCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _basic(self, name="demo"):
        return Project(name=name, tracks=[
            Track(name="bass", type="midi", content="C E G"),
        ], tempo=100.0, time_signature="5/4", key="Gm")


class TestCreate(_IsolatedCase):
    def test_creates_files(self):
        root = layout.create(self._basic(), self.root / "demo")
        self.assertTrue((root / "project.json").is_file())
        self.assertTrue((root / "README.md").is_file())
        self.assertTrue((root / ".gitignore").is_file())

    def test_creates_subdirs(self):
        root = layout.create(self._basic(), self.root / "demo")
        for sub in ("tracks", "patterns", "samples", "renders"):
            self.assertTrue((root / sub).is_dir(), sub)

    def test_project_json_roundtrip(self):
        p = self._basic()
        root = layout.create(p, self.root / "demo")
        data = json.loads((root / "project.json").read_text())
        self.assertEqual(data["name"], "demo")
        self.assertEqual(data["tempo"], 100.0)
        self.assertEqual(data["time_signature"], "5/4")
        self.assertEqual(data["key"], "Gm")
        self.assertEqual(len(data["tracks"]), 1)
        self.assertEqual(data["tracks"][0]["name"], "bass")

    def test_readme_mentions_tracks(self):
        root = layout.create(self._basic(), self.root / "demo")
        text = (root / "README.md").read_text()
        self.assertIn("# demo", text)
        self.assertIn("bass", text)

    def test_gitignore_ignores_renders(self):
        root = layout.create(self._basic(), self.root / "demo")
        text = (root / ".gitignore").read_text()
        self.assertIn("renders/", text)
        self.assertIn("*.wav", text)

    def test_empty_target_ok(self):
        target = self.root / "empty"
        target.mkdir()
        root = layout.create(self._basic(), target)
        self.assertTrue((root / "project.json").is_file())

    def test_nonempty_target_rejected(self):
        target = self.root / "busy"
        target.mkdir()
        (target / "existing.txt").write_text("x")
        with self.assertRaises(layout.LayoutError):
            layout.create(self._basic(), target)

    def test_file_target_rejected(self):
        target = self.root / "afile"
        target.write_text("x")
        with self.assertRaises(layout.LayoutError):
            layout.create(self._basic(), target)

    def test_rejects_non_project(self):
        with self.assertRaises(layout.LayoutError):
            layout.create("not a project", self.root / "demo")


class TestRead(_IsolatedCase):
    def test_roundtrip(self):
        p = self._basic()
        root = layout.create(p, self.root / "demo")
        loaded = layout.read(root)
        self.assertEqual(loaded.name, p.name)
        self.assertEqual(loaded.tempo, p.tempo)
        self.assertEqual(loaded.time_signature, p.time_signature)
        self.assertEqual(len(loaded.tracks), 1)
        self.assertEqual(loaded.tracks[0].name, "bass")

    def test_missing_project_json(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(layout.LayoutError):
            layout.read(empty)

    def test_not_a_directory(self):
        f = self.root / "afile"
        f.write_text("x")
        with self.assertRaises(layout.LayoutError):
            layout.read(f)

    def test_corrupt_json(self):
        root = self.root / "demo"
        root.mkdir()
        (root / "project.json").write_text("{not valid json")
        with self.assertRaises(layout.LayoutError):
            layout.read(root)

    def test_invalid_project_data(self):
        root = self.root / "demo"
        root.mkdir()
        (root / "project.json").write_text(json.dumps({"tempo": 120}))
        with self.assertRaises(layout.LayoutError):
            layout.read(root)


class TestIsProject(_IsolatedCase):
    def test_true_on_project_dir(self):
        root = layout.create(self._basic(), self.root / "demo")
        self.assertTrue(layout.is_project(root))

    def test_false_on_empty_dir(self):
        d = self.root / "empty"
        d.mkdir()
        self.assertFalse(layout.is_project(d))

    def test_false_on_missing_path(self):
        self.assertFalse(layout.is_project(self.root / "nope"))


if __name__ == "__main__":
    unittest.main()
