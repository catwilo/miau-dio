"""Tests for miau_dio.backends.backend -- stdlib unittest only.

Covers the registry contract (names, package names per platform, source
recipes) and the is_installed() detector. No binary is installed, no
network is touched.
"""
import shutil
import unittest
from unittest import mock

from miau_dio.backends.backend import (
    BACKENDS, PROFILES, Backend, Source, is_installed,
)


class TestRegistryShape(unittest.TestCase):
    def test_known_backends_present(self):
        self.assertEqual(set(BACKENDS.keys()),
                         {"abcmidi", "timidity", "sox"})

    def test_all_entries_are_backend(self):
        for b in BACKENDS.values():
            self.assertIsInstance(b, Backend)

    def test_backend_is_frozen(self):
        b = BACKENDS["sox"]
        with self.assertRaises(Exception):
            b.name = "other"  # type: ignore[misc]


class TestAbcmidiEntry(unittest.TestCase):
    def test_binary_name(self):
        self.assertEqual(BACKENDS["abcmidi"].name, "abc2midi")

    def test_has_apt_package(self):
        self.assertEqual(BACKENDS["abcmidi"].apt_pkg, "abcmidi")

    def test_has_no_termux_package(self):
        self.assertIsNone(BACKENDS["abcmidi"].termux_pkg)

    def test_has_source_recipe(self):
        src = BACKENDS["abcmidi"].source
        self.assertIsInstance(src, Source)
        self.assertTrue(src.git_url.startswith("https://"))
        self.assertEqual(src.binary, "abc2midi")

    def test_source_build_produces_binary(self):
        src = BACKENDS["abcmidi"].source
        self.assertIn("abc2midi", src.build)


class TestTimidityEntry(unittest.TestCase):
    def test_binary_name(self):
        self.assertEqual(BACKENDS["timidity"].name, "timidity")

    def test_different_packages_per_platform(self):
        b = BACKENDS["timidity"]
        self.assertEqual(b.apt_pkg, "timidity")
        self.assertEqual(b.termux_pkg, "timidity++")

    def test_no_source_recipe(self):
        self.assertIsNone(BACKENDS["timidity"].source)


class TestSoxEntry(unittest.TestCase):
    def test_binary_name(self):
        self.assertEqual(BACKENDS["sox"].name, "sox")

    def test_same_package_both_platforms(self):
        b = BACKENDS["sox"]
        self.assertEqual(b.apt_pkg, "sox")
        self.assertEqual(b.termux_pkg, "sox")


class TestProfiles(unittest.TestCase):
    def test_known_profiles(self):
        self.assertEqual(set(PROFILES.keys()),
                         {"minimal", "playback", "full"})

    def test_minimal_only_abcmidi(self):
        self.assertEqual(PROFILES["minimal"], ["abcmidi"])

    def test_playback_adds_timidity(self):
        self.assertEqual(PROFILES["playback"], ["abcmidi", "timidity"])

    def test_full_adds_sox(self):
        self.assertEqual(PROFILES["full"],
                         ["abcmidi", "timidity", "sox"])

    def test_every_profile_entry_exists_in_registry(self):
        for name, members in PROFILES.items():
            for member in members:
                self.assertIn(member, BACKENDS,
                              f"profile {name} refers to unknown {member}")


class TestIsInstalled(unittest.TestCase):
    def test_true_when_on_path(self):
        with mock.patch.object(shutil, "which", return_value="/usr/bin/sox"):
            self.assertTrue(is_installed(BACKENDS["sox"]))

    def test_false_when_missing(self):
        with mock.patch.object(shutil, "which", return_value=None):
            self.assertFalse(is_installed(BACKENDS["sox"]))

    def test_checks_backend_binary_name(self):
        with mock.patch.object(shutil, "which", return_value=None) as m:
            is_installed(BACKENDS["abcmidi"])
            m.assert_called_once_with("abc2midi")


if __name__ == "__main__":
    unittest.main()
