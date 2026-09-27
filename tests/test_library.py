"""Tests for miau_dio.instruments.library -- stdlib unittest only."""
import json
import os
import pathlib
import tempfile
import unittest

from miau_dio.instruments import library
from miau_dio.instruments.library import LibraryError
from miau_dio.instruments.model import Instrument


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

    def _index_file(self) -> pathlib.Path:
        return pathlib.Path(self._tmp.name) / "miau-dio" / "instruments" / "index.json"


class TestAddGetList(_IsolatedCase):
    def test_empty_library(self):
        self.assertEqual(library.list_instruments(), [])
        self.assertFalse(library.exists("piano"))

    def test_add_and_get(self):
        library.add(Instrument(name="piano", program=0, family="keys"))
        got = library.get("piano")
        self.assertEqual(got.program, 0)
        self.assertEqual(got.family, "keys")

    def test_add_duplicate_raises(self):
        library.add(Instrument(name="piano", program=0))
        with self.assertRaises(LibraryError) as cm:
            library.add(Instrument(name="piano", program=5))
        self.assertIn("already exists", str(cm.exception))

    def test_add_non_instrument_raises(self):
        with self.assertRaises(LibraryError) as cm:
            library.add({"name": "x", "program": 0})  # type: ignore[arg-type]
        self.assertIn("expected Instrument", str(cm.exception))

    def test_get_missing_raises_keyerror(self):
        with self.assertRaises(KeyError):
            library.get("piano")

    def test_list_sorted_by_name(self):
        for n in ("violin", "piano", "cello"):
            library.add(Instrument(name=n, program=0))
        names = [i.name for i in library.list_instruments()]
        self.assertEqual(names, ["cello", "piano", "violin"])

    def test_index_file_created(self):
        library.add(Instrument(name="piano", program=0))
        self.assertTrue(self._index_file().is_file())

    def test_per_instrument_file_created(self):
        library.add(Instrument(name="piano", program=0))
        d = pathlib.Path(self._tmp.name) / "miau-dio" / "instruments"
        self.assertTrue((d / "piano.json").is_file())


class TestUpdate(_IsolatedCase):
    def test_update_program(self):
        library.add(Instrument(name="piano", program=0))
        updated = library.update("piano", program=40)
        self.assertEqual(updated.program, 40)
        self.assertEqual(library.get("piano").program, 40)

    def test_update_family(self):
        library.add(Instrument(name="piano", program=0))
        library.update("piano", family="keys")
        self.assertEqual(library.get("piano").family, "keys")

    def test_update_missing_raises_keyerror(self):
        with self.assertRaises(KeyError):
            library.update("piano", program=5)

    def test_update_rejects_rename(self):
        library.add(Instrument(name="piano", program=0))
        with self.assertRaises(LibraryError) as cm:
            library.update("piano", name="grand")
        self.assertIn("rename must go through", str(cm.exception))

    def test_update_invalid_program_propagates(self):
        library.add(Instrument(name="piano", program=0))
        with self.assertRaises(Exception):
            library.update("piano", program=999)
        # original untouched
        self.assertEqual(library.get("piano").program, 0)


class TestRename(_IsolatedCase):
    def test_rename_moves_record(self):
        library.add(Instrument(name="piano", program=0, family="keys"))
        moved = library.rename("piano", "grand")
        self.assertEqual(moved.name, "grand")
        self.assertFalse(library.exists("piano"))
        self.assertEqual(library.get("grand").program, 0)

    def test_rename_removes_old_file(self):
        library.add(Instrument(name="piano", program=0))
        library.rename("piano", "grand")
        d = pathlib.Path(self._tmp.name) / "miau-dio" / "instruments"
        self.assertFalse((d / "piano.json").exists())
        self.assertTrue((d / "grand.json").is_file())

    def test_rename_missing_raises_keyerror(self):
        with self.assertRaises(KeyError):
            library.rename("piano", "grand")

    def test_rename_to_existing_raises(self):
        library.add(Instrument(name="piano", program=0))
        library.add(Instrument(name="cello", program=42))
        with self.assertRaises(LibraryError) as cm:
            library.rename("piano", "cello")
        self.assertIn("already exists", str(cm.exception))


class TestRemove(_IsolatedCase):
    def test_remove_existing(self):
        library.add(Instrument(name="piano", program=0))
        library.remove("piano")
        self.assertFalse(library.exists("piano"))

    def test_remove_missing_is_noop(self):
        library.remove("piano")  # no error

    def test_remove_deletes_file(self):
        library.add(Instrument(name="piano", program=0))
        library.remove("piano")
        d = pathlib.Path(self._tmp.name) / "miau-dio" / "instruments"
        self.assertFalse((d / "piano.json").exists())


class TestDuplicate(_IsolatedCase):
    def test_default_suffix(self):
        library.add(Instrument(name="piano", program=0, family="keys"))
        dup = library.duplicate("piano")
        self.assertEqual(dup.name, "piano (copy)")
        self.assertEqual(dup.program, 0)
        self.assertEqual(dup.family, "keys")

    def test_explicit_name(self):
        library.add(Instrument(name="piano", program=0))
        dup = library.duplicate("piano", "piano2")
        self.assertEqual(dup.name, "piano2")

    def test_duplicate_missing_raises_keyerror(self):
        with self.assertRaises(KeyError):
            library.duplicate("piano")

    def test_duplicate_into_existing_raises(self):
        library.add(Instrument(name="piano", program=0))
        library.add(Instrument(name="piano2", program=0))
        with self.assertRaises(LibraryError):
            library.duplicate("piano", "piano2")


class TestFamilies(_IsolatedCase):
    def test_distinct_sorted(self):
        for n, f in (("piano", "keys"), ("cello", "strings"),
                     ("violin", "strings"), ("drum", "")):
            library.add(Instrument(name=n, program=0, family=f))
        self.assertEqual(library.families(), ["keys", "strings"])

    def test_empty_library(self):
        self.assertEqual(library.families(), [])


class TestSafeName(_IsolatedCase):
    def test_slash_rejected_on_add(self):
        with self.assertRaises(LibraryError):
            library.add(Instrument(name="a/b", program=0))

    def test_backslash_rejected(self):
        with self.assertRaises(LibraryError):
            library.add(Instrument(name="a\\b", program=0))

    def test_dot_rejected(self):
        with self.assertRaises(LibraryError):
            library.add(Instrument(name=".", program=0))

    def test_dotdot_rejected(self):
        with self.assertRaises(LibraryError):
            library.add(Instrument(name="..", program=0))

    def test_leading_dot_rejected(self):
        with self.assertRaises(LibraryError):
            library.add(Instrument(name=".hidden", program=0))

    def test_get_unsafe_raises(self):
        with self.assertRaises(LibraryError):
            library.get("../etc/passwd")

    def test_rename_unsafe_new_raises(self):
        library.add(Instrument(name="piano", program=0))
        with self.assertRaises(LibraryError):
            library.rename("piano", "a/b")


class TestCorruptionDetection(_IsolatedCase):
    def test_corrupt_index_raises(self):
        p = self._index_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json")
        with self.assertRaises(LibraryError) as cm:
            library.list_instruments()
        self.assertIn("corrupt JSON", str(cm.exception))

    def test_index_not_object_raises(self):
        p = self._index_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("[1, 2, 3]")
        with self.assertRaises(LibraryError) as cm:
            library.list_instruments()
        self.assertIn("JSON object", str(cm.exception))


class TestAtomicWrite(_IsolatedCase):
    def test_no_tmp_file_left_behind(self):
        library.add(Instrument(name="piano", program=0))
        d = pathlib.Path(self._tmp.name) / "miau-dio" / "instruments"
        leftovers = [p for p in d.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_index_content_is_valid_json(self):
        library.add(Instrument(name="piano", program=3, family="keys"))
        data = json.loads(self._index_file().read_text())
        self.assertEqual(data, {"piano": {"program": 3, "family": "keys"}})


if __name__ == "__main__":
    unittest.main()
