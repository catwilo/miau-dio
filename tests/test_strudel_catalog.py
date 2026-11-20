"""Tests for the Strudel sample catalog (task #174) -- stdlib unittest."""
import unittest

from miau_dio.strudel import catalog


class TestCatalogShape(unittest.TestCase):
    def test_known_packs_present(self):
        names = set(catalog.CATALOG.keys())
        # The catalog is expected to ship with these packs.
        self.assertTrue({"uzu", "piano", "dirt", "mridangam"} <= names)

    def test_all_entries_are_pack(self):
        for p in catalog.CATALOG.values():
            self.assertIsInstance(p, catalog.Pack)

    def test_pack_is_frozen(self):
        p = catalog.CATALOG["uzu"]
        with self.assertRaises(Exception):
            p.name = "other"  # type: ignore[misc]

    def test_each_pack_has_manifest_url(self):
        for p in catalog.CATALOG.values():
            self.assertTrue(p.manifest_url.startswith("https://"),
                            f"{p.name} manifest must be https")

    def test_each_pack_has_positive_size(self):
        for p in catalog.CATALOG.values():
            self.assertGreater(p.approx_mb, 0)

    def test_each_pack_has_tags(self):
        for p in catalog.CATALOG.values():
            self.assertTrue(p.tags, f"{p.name} has no tags")


class TestGet(unittest.TestCase):
    def test_existing(self):
        p = catalog.get("uzu")
        self.assertEqual(p.name, "uzu")

    def test_missing_raises(self):
        with self.assertRaises(KeyError):
            catalog.get("nonexistent")


class TestAllPacks(unittest.TestCase):
    def test_sorted_by_name(self):
        names = [p.name for p in catalog.all_packs()]
        self.assertEqual(names, sorted(names))




class TestResolveSamples(unittest.TestCase):
    def test_none(self):
        self.assertEqual(catalog.resolve_samples("none"), [])
        self.assertEqual(catalog.resolve_samples(""), [])

    def test_group_drums(self):
        self.assertEqual(catalog.resolve_samples("drums"), ["uzu", "dirt"])

    def test_group_brass(self):
        self.assertEqual(
            catalog.resolve_samples("brass"),
            ["trumpet", "trumpet_stac", "trombone", "trombone_stac"],
        )

    def test_group_strings(self):
        self.assertEqual(catalog.resolve_samples("strings"), ["guitar"])

    def test_group_all_vendored(self):
        names = catalog.resolve_samples("all")
        self.assertEqual(sorted(names), sorted(catalog.GROUPS["all"]))

    def test_comma_list(self):
        self.assertEqual(catalog.resolve_samples("uzu,guitar"),
                         ["uzu", "guitar"])

    def test_comma_list_with_spaces(self):
        self.assertEqual(catalog.resolve_samples("uzu , guitar"),
                         ["uzu", "guitar"])

    def test_unknown_name_raises(self):
        with self.assertRaises(KeyError):
            catalog.resolve_samples("nope")


if __name__ == "__main__":
    unittest.main()
