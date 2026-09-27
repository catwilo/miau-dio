"""Tests for miau_dio.instruments.model -- stdlib unittest only."""
import unittest

from miau_dio.instruments.model import (
    FAMILY_MAX, GM_PROGRAM_MAX, GM_PROGRAM_MIN, NAME_MAX,
    Instrument, InstrumentError,
)


class TestConstruction(unittest.TestCase):
    def test_minimal_fields(self):
        i = Instrument(name="piano", program=0)
        self.assertEqual(i.name, "piano")
        self.assertEqual(i.program, 0)
        self.assertEqual(i.family, "")

    def test_with_family(self):
        i = Instrument(name="cello", program=42, family="strings")
        self.assertEqual(i.family, "strings")

    def test_is_frozen(self):
        i = Instrument(name="piano", program=0)
        with self.assertRaises(Exception):
            i.name = "other"  # type: ignore[misc]

    def test_equality_by_value(self):
        self.assertEqual(Instrument(name="piano", program=0),
                         Instrument(name="piano", program=0))


class TestNameValidation(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="", program=0)
        self.assertIn("must not be empty", str(cm.exception))

    def test_whitespace_only_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="   ", program=0)
        self.assertIn("must not be empty", str(cm.exception))

    def test_strips_whitespace(self):
        i = Instrument(name="  piano  ", program=0)
        self.assertEqual(i.name, "piano")

    def test_max_length_ok(self):
        i = Instrument(name="a" * NAME_MAX, program=0)
        self.assertEqual(len(i.name), NAME_MAX)

    def test_over_max_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="a" * (NAME_MAX + 1), program=0)
        self.assertIn("name must be <=", str(cm.exception))

    def test_non_string_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name=123, program=0)  # type: ignore[arg-type]
        self.assertIn("must be a string", str(cm.exception))


class TestProgramValidation(unittest.TestCase):
    def test_min_ok(self):
        self.assertEqual(Instrument(name="x", program=GM_PROGRAM_MIN).program,
                         GM_PROGRAM_MIN)

    def test_max_ok(self):
        self.assertEqual(Instrument(name="x", program=GM_PROGRAM_MAX).program,
                         GM_PROGRAM_MAX)

    def test_below_min_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="x", program=-1)
        self.assertIn("out of GM range", str(cm.exception))

    def test_above_max_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="x", program=128)
        self.assertIn("out of GM range", str(cm.exception))

    def test_bool_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="x", program=True)  # type: ignore[arg-type]
        self.assertIn("not a bool", str(cm.exception))

    def test_non_int_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="x", program="0")  # type: ignore[arg-type]
        self.assertIn("must be an int", str(cm.exception))


class TestFamilyValidation(unittest.TestCase):
    def test_empty_allowed(self):
        self.assertEqual(Instrument(name="x", program=0).family, "")

    def test_strips_whitespace(self):
        i = Instrument(name="x", program=0, family="  strings  ")
        self.assertEqual(i.family, "strings")

    def test_max_length_ok(self):
        i = Instrument(name="x", program=0, family="f" * FAMILY_MAX)
        self.assertEqual(len(i.family), FAMILY_MAX)

    def test_over_max_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="x", program=0, family="f" * (FAMILY_MAX + 1))
        self.assertIn("family must be <=", str(cm.exception))

    def test_non_string_rejected(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument(name="x", program=0, family=1)  # type: ignore[arg-type]
        self.assertIn("must be a string", str(cm.exception))


class TestSerialisation(unittest.TestCase):
    def test_to_dict_roundtrip(self):
        i = Instrument(name="piano", program=0, family="keys")
        self.assertEqual(Instrument.from_dict(i.to_dict()), i)

    def test_to_dict_keys(self):
        d = Instrument(name="piano", program=0).to_dict()
        self.assertEqual(set(d.keys()), {"name", "program", "family"})

    def test_from_dict_missing_family_defaults_empty(self):
        i = Instrument.from_dict({"name": "piano", "program": 0})
        self.assertEqual(i.family, "")

    def test_from_dict_missing_required_raises(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument.from_dict({"name": "piano"})
        self.assertIn("missing fields", str(cm.exception))
        self.assertIn("program", str(cm.exception))

    def test_from_dict_non_dict_raises(self):
        with self.assertRaises(InstrumentError) as cm:
            Instrument.from_dict(["piano", 0])  # type: ignore[arg-type]
        self.assertIn("must be a dict", str(cm.exception))

    def test_from_dict_invalid_field_raises(self):
        with self.assertRaises(InstrumentError):
            Instrument.from_dict({"name": "piano", "program": 200})


if __name__ == "__main__":
    unittest.main()
