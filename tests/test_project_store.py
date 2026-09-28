"""Tests for the Project store (task #171) -- stdlib unittest only."""
import os
import tempfile
import unittest

from miau_dio.project import store
from miau_dio.project.model import Project, Track


class _IsolatedCase(unittest.TestCase):
    """Every test runs against a fresh XDG_DATA_HOME in a tmpdir."""

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


class TestAdd(_IsolatedCase):
    def test_returns_id_and_project(self):
        p = Project(name="demo")
        iid, stored = store.add(p)
        self.assertIsInstance(iid, str)
        self.assertEqual(len(iid), 8)
        self.assertEqual(stored.name, "demo")
        self.assertTrue(stored.created)
        self.assertTrue(stored.modified)
        self.assertTrue(store.exists(iid))

    def test_keeps_tracks(self):
        p = Project(name="demo", tracks=[
            Track(name="bass", type="midi", content="C E G"),
        ])
        iid, _ = store.add(p)
        loaded = store.get(iid)
        self.assertEqual(len(loaded.tracks), 1)
        self.assertEqual(loaded.tracks[0].name, "bass")
        self.assertEqual(loaded.tracks[0].content, "C E G")

    def test_two_same_name_get_different_ids(self):
        a, _ = store.add(Project(name="demo"))
        b, _ = store.add(Project(name="demo"))
        self.assertNotEqual(a, b)


class TestList(_IsolatedCase):
    def test_sorted_by_name(self):
        store.add(Project(name="zeta"))
        store.add(Project(name="alpha"))
        store.add(Project(name="mid"))
        names = [e["name"] for _, e in store.list_projects()]
        self.assertEqual(names, ["alpha", "mid", "zeta"])

    def test_includes_track_count(self):
        iid, _ = store.add(Project(name="demo", tracks=[
            Track(name="bass", type="midi"),
            Track(name="drum", type="pattern"),
        ]))
        items = store.list_projects()
        self.assertEqual(items[0][0], iid)
        self.assertEqual(items[0][1]["track_count"], 2)


class TestGet(_IsolatedCase):
    def test_missing_raises(self):
        with self.assertRaises(KeyError):
            store.get("deadbeef")

    def test_unsafe_id_rejected(self):
        with self.assertRaises(store.ProjectStoreError):
            store.get("../etc/passwd")


class TestUpdate(_IsolatedCase):
    def test_changes_modified(self):
        iid, stored = store.add(Project(name="demo"))
        updated = store.update(iid, tempo=140.0)
        self.assertEqual(updated.tempo, 140.0)
        self.assertEqual(updated.created, stored.created)
        self.assertGreaterEqual(updated.modified, stored.modified)

    def test_rename_keeps_id(self):
        iid, _ = store.add(Project(name="demo"))
        renamed = store.rename(iid, "demo v2")
        self.assertEqual(renamed.name, "demo v2")
        self.assertTrue(store.exists(iid))
        self.assertEqual(store.get(iid).name, "demo v2")


class TestRemove(_IsolatedCase):
    def test_is_idempotent(self):
        iid, _ = store.add(Project(name="demo"))
        store.remove(iid)
        self.assertFalse(store.exists(iid))
        store.remove(iid)  # second call must not raise


class TestIsolation(_IsolatedCase):
    def test_reload_does_not_see_in_memory_append(self):
        iid, _ = store.add(Project(name="demo"))
        p = store.get(iid)
        p.tracks.append(Track(name="extra", type="midi"))
        reloaded = store.get(iid)
        self.assertEqual(len(reloaded.tracks), 0)


if __name__ == "__main__":
    unittest.main()
