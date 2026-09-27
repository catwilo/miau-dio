"""Tests for miau_dio.store.store -- stdlib unittest only.

The store module binds DATA and INDEX at import time from
XDG_DATA_HOME. Each test rebinds both to a fresh TemporaryDirectory so
no test touches the user's real data directory.
"""
import json
import os
import pathlib
import tempfile
import unittest

from miau_dio.store import store


class _StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        data = pathlib.Path(self._tmp.name) / "miau-dio"
        (data / "abc").mkdir(parents=True, exist_ok=True)
        (data / "audio").mkdir(parents=True, exist_ok=True)
        self._prev_data = store.DATA
        self._prev_index = store.INDEX
        store.DATA = data
        store.INDEX = data / "index.json"

    def tearDown(self):
        store.DATA = self._prev_data
        store.INDEX = self._prev_index
        self._tmp.cleanup()

    def _abc(self, body="X:1\nK:C\nC D E F|\n", name="src.abc") -> str:
        p = pathlib.Path(self._tmp.name) / name
        p.write_text(body)
        return str(p)

    def _add(self, name="demo", tags=None, notes=""):
        return store.add(name, self._abc(name=f"{name}.abc"),
                         tags or [], notes)


class TestAdd(_StoreCase):
    def test_add_returns_idea(self):
        idea = self._add()
        self.assertEqual(idea.name, "demo")
        self.assertTrue(idea.id)
        self.assertEqual(len(idea.id), 8)

    def test_add_writes_abc_file(self):
        idea = self._add()
        self.assertTrue(store.abc_path(idea.id).is_file())
        self.assertEqual(store.abc_path(idea.id).read_text(),
                         "X:1\nK:C\nC D E F|\n")

    def test_add_writes_index(self):
        self._add()
        self.assertTrue(store.INDEX.is_file())

    def test_add_records_hash(self):
        idea = self._add()
        self.assertEqual(len(idea.abc_hash), 40)

    def test_add_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            store.add("x", "/nonexistent.abc", [], "")

    def test_add_with_tags_and_notes(self):
        idea = self._add(tags=["a", "b"], notes="hi")
        self.assertEqual(idea.tags, ["a", "b"])
        self.assertEqual(idea.notes, "hi")

    def test_add_duplicate_name_gets_distinct_id(self):
        a = self._add()
        b = self._add()
        self.assertNotEqual(a.id, b.id)


class TestGet(_StoreCase):
    def test_get_roundtrip(self):
        added = self._add()
        got = store.get(added.id)
        self.assertEqual(got.name, "demo")
        self.assertEqual(got.id, added.id)

    def test_get_missing_raises(self):
        with self.assertRaises(KeyError):
            store.get("deadbeef")


class TestAllIdeas(_StoreCase):
    def test_empty(self):
        self.assertEqual(store.all_ideas(), [])

    def test_returns_all(self):
        for n in ("a", "b", "c"):
            self._add(name=n)
        names = sorted(i.name for i in store.all_ideas())
        self.assertEqual(names, ["a", "b", "c"])


class TestUpdate(_StoreCase):
    def test_update_name(self):
        idea = self._add()
        store.update(idea.id, name="renamed")
        self.assertEqual(store.get(idea.id).name, "renamed")

    def test_update_touches_modified(self):
        idea = self._add()
        before = store.get(idea.id).modified
        import time
        time.sleep(1.1)
        store.update(idea.id, notes="x")
        after = store.get(idea.id).modified
        self.assertNotEqual(before, after)

    def test_update_missing_raises(self):
        with self.assertRaises(KeyError):
            store.update("deadbeef", name="x")


class TestRemove(_StoreCase):
    def test_remove_clears_index_and_files(self):
        idea = self._add()
        store.remove(idea.id)
        self.assertEqual(store.all_ideas(), [])
        self.assertFalse(store.abc_path(idea.id).exists())

    def test_remove_missing_is_noop(self):
        store.remove("deadbeef")

    def test_remove_clears_audio_cache(self):
        idea = self._add()
        audio = store.audio_path(idea.id)
        audio.write_bytes(b"fake")
        store.remove(idea.id)
        self.assertFalse(audio.exists())


class TestDuplicate(_StoreCase):
    def test_duplicate_default_name(self):
        idea = self._add()
        dup = store.duplicate(idea.id)
        self.assertEqual(dup.name, "demo (copy)")
        self.assertNotEqual(dup.id, idea.id)

    def test_duplicate_explicit_name(self):
        idea = self._add()
        dup = store.duplicate(idea.id, "demo2")
        self.assertEqual(dup.name, "demo2")

    def test_duplicate_copies_abc_body(self):
        idea = self._add()
        dup = store.duplicate(idea.id)
        self.assertEqual(store.abc_path(dup.id).read_text(),
                         store.abc_path(idea.id).read_text())

    def test_duplicate_copies_tags_and_notes(self):
        idea = self._add(tags=["t1"], notes="n1")
        dup = store.duplicate(idea.id)
        self.assertEqual(dup.tags, ["t1"])
        self.assertEqual(dup.notes, "n1")


class TestSearch(_StoreCase):
    def test_search_empty_returns_all(self):
        for n in ("a", "b"):
            self._add(name=n)
        self.assertEqual(len(store.search()), 2)

    def test_search_by_name(self):
        self._add(name="alpha")
        self._add(name="beta")
        hits = store.search("alph")
        self.assertEqual([i.name for i in hits], ["alpha"])

    def test_search_by_notes(self):
        self._add(name="alpha", notes="something")
        self._add(name="beta", notes="other")
        hits = store.search("some")
        self.assertEqual([i.name for i in hits], ["alpha"])

    def test_search_case_insensitive(self):
        self._add(name="Alpha")
        self.assertEqual(len(store.search("ALP")), 1)

    def test_filter_by_tag(self):
        self._add(name="a", tags=["wip"])
        self._add(name="b", tags=["done"])
        hits = store.search(tag="wip")
        self.assertEqual([i.name for i in hits], ["a"])

    def test_combined_filters(self):
        self._add(name="alpha", tags=["wip"])
        self._add(name="beta", tags=["wip"])
        self._add(name="alpha", tags=["done"])
        hits = store.search("alph", "wip")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].name, "alpha")


class TestAllTags(_StoreCase):
    def test_empty(self):
        self.assertEqual(store.all_tags(), set())

    def test_union_distinct(self):
        self._add(name="a", tags=["x", "y"])
        self._add(name="b", tags=["y", "z"])
        self.assertEqual(store.all_tags(), {"x", "y", "z"})


class TestAtomicIndex(_StoreCase):
    def test_index_is_valid_json(self):
        self._add()
        data = json.loads(store.INDEX.read_text())
        self.assertIsInstance(data, dict)
        self.assertEqual(len(data), 1)

    def test_no_tmp_left_behind(self):
        self._add()
        leftovers = list(store.DATA.glob("*.tmp"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
