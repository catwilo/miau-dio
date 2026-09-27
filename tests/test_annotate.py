"""Tests for miau_dio.assignment.annotate -- stdlib unittest only."""
import random
import unittest

from miau_dio.assignment.annotate import (
    FIXED, RANDOM, AssignmentError, annotate,
)

SIMPLE = "X:1\nT:demo\nM:4/4\nL:1/4\nK:C\nC D E F|\n"


class TestFixed(unittest.TestCase):
    def test_inserts_after_K(self):
        out = annotate(SIMPLE, FIXED, program=40)
        lines = out.splitlines()
        k_idx = lines.index("K:C")
        self.assertEqual(lines[k_idx + 1], "%%MIDI program 40")
        self.assertEqual(lines[k_idx + 2], "C D E F|")

    def test_program_zero_ok(self):
        out = annotate(SIMPLE, FIXED, program=0)
        self.assertIn("%%MIDI program 0", out.splitlines())

    def test_program_127_ok(self):
        out = annotate(SIMPLE, FIXED, program=127)
        self.assertIn("%%MIDI program 127", out.splitlines())

    def test_program_out_of_range_rejected(self):
        with self.assertRaises(AssignmentError):
            annotate(SIMPLE, FIXED, program=128)

    def test_program_bool_rejected(self):
        with self.assertRaises(AssignmentError):
            annotate(SIMPLE, FIXED, program=True)

    def test_missing_program_rejected(self):
        with self.assertRaises(AssignmentError) as cm:
            annotate(SIMPLE, FIXED)
        self.assertIn("requires program", str(cm.exception))

    def test_missing_K_rejected(self):
        with self.assertRaises(AssignmentError) as cm:
            annotate("X:1\nT:demo\n", FIXED, program=0)
        self.assertIn("no K:", str(cm.exception))

    def test_pre_existing_program_overridden(self):
        # ABC semantics: the last %%MIDI program before the body wins, so
        # annotate(program=40) must place its directive AFTER the existing
        # one to actually override it.
        src = "X:1\nK:C\n%%MIDI program 5\nC D E F|\n"
        out = annotate(src, FIXED, program=40)
        lines = out.splitlines()
        k_idx = lines.index("K:C")
        self.assertEqual(lines[k_idx + 1], "%%MIDI program 5")
        self.assertEqual(lines[k_idx + 2], "%%MIDI program 40")

    def test_preserves_headers_and_body(self):
        out = annotate(SIMPLE, FIXED, program=0)
        self.assertIn("X:1", out)
        self.assertIn("T:demo", out)
        self.assertIn("M:4/4", out)
        self.assertIn("L:1/4", out)
        self.assertIn("C D E F|", out)


class TestFixedEdge(unittest.TestCase):
    def test_trailing_newline_preserved(self):
        out = annotate(SIMPLE, FIXED, program=0)
        self.assertTrue(out.endswith("\n"))

    def test_no_trailing_newline_preserved(self):
        out = annotate(SIMPLE.rstrip("\n"), FIXED, program=0)
        self.assertFalse(out.endswith("\n"))


class TestRandom(unittest.TestCase):
    def test_program_count_equals_note_count(self):
        out = annotate(SIMPLE, RANDOM, rng=random.Random(0))
        directives = [l for l in out.splitlines()
                      if l.startswith("%%MIDI program")]
        self.assertEqual(len(directives), 4)

    def test_reproducible_with_seed(self):
        a = annotate(SIMPLE, RANDOM, rng=random.Random(42))
        b = annotate(SIMPLE, RANDOM, rng=random.Random(42))
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        a = annotate(SIMPLE, RANDOM, rng=random.Random(1))
        b = annotate(SIMPLE, RANDOM, rng=random.Random(2))
        self.assertNotEqual(a, b)

    def test_pool_respected(self):
        out = annotate(SIMPLE, RANDOM, programs=[10], rng=random.Random(0))
        directives = [l for l in out.splitlines()
                      if l.startswith("%%MIDI program")]
        self.assertTrue(all(d == "%%MIDI program 10" for d in directives))

    def test_single_program_via_program_kwarg(self):
        out = annotate(SIMPLE, RANDOM, program=7, rng=random.Random(0))
        directives = [l for l in out.splitlines()
                      if l.startswith("%%MIDI program")]
        self.assertTrue(all(d == "%%MIDI program 7" for d in directives))

    def test_invalid_pool_entry_rejected(self):
        with self.assertRaises(AssignmentError):
            annotate(SIMPLE, RANDOM, programs=[0, 128], rng=random.Random(0))

    def test_empty_body_rejected(self):
        with self.assertRaises(AssignmentError) as cm:
            annotate("X:1\nK:C\n", RANDOM, rng=random.Random(0))
        self.assertIn("no notes", str(cm.exception))

    def test_headers_preserved(self):
        out = annotate(SIMPLE, RANDOM, programs=[5], rng=random.Random(0))
        for header in ("X:1", "T:demo", "M:4/4", "L:1/4", "K:C"):
            self.assertIn(header, out)

    def test_octave_markers_preserved(self):
        src = "X:1\nK:C\nc'' C,,\n"
        out = annotate(src, RANDOM, program=0, rng=random.Random(0))
        self.assertIn("c''", out)
        self.assertIn("C,,", out)

    def test_accidentals_preserved(self):
        src = "X:1\nK:C\n^C _D =E\n"
        out = annotate(src, RANDOM, program=0, rng=random.Random(0))
        self.assertIn("^C", out)
        self.assertIn("_D", out)
        self.assertIn("=E", out)

    def test_duration_preserved(self):
        src = "X:1\nK:C\nC3/2 D/ E2\n"
        out = annotate(src, RANDOM, program=0, rng=random.Random(0))
        self.assertIn("C3/2", out)
        self.assertIn("D/", out)
        self.assertIn("E2", out)

    def test_barlines_emitted_on_their_own_line(self):
        out = annotate(SIMPLE, RANDOM, program=0, rng=random.Random(0))
        self.assertIn("|", out.splitlines())

    def test_min_duration_filters_short_notes(self):
        # 4/4, L:1/4: durations are in units of 1/4. C=1, D=1, E=0.5, F=0.5
        src = "X:1\nK:C\nC D E/ F/\n"
        out = annotate(src, RANDOM, program=0, min_duration=1.0,
                       rng=random.Random(0))
        # Only C and D qualify; E and F reuse the previous program.
        directives = [l for l in out.splitlines()
                      if l.startswith("%%MIDI program")]
        # 1 for C + 1 for D; E and F reuse -> 2 total
        self.assertEqual(len(directives), 2)

    def test_min_duration_none_emits_for_all(self):
        src = "X:1\nK:C\nC D E/ F/\n"
        out = annotate(src, RANDOM, program=0, min_duration=None,
                       rng=random.Random(0))
        directives = [l for l in out.splitlines()
                      if l.startswith("%%MIDI program")]
        self.assertEqual(len(directives), 4)

    def test_first_note_below_filter_still_gets_program(self):
        src = "X:1\nK:C\nE/ F/\n"
        out = annotate(src, RANDOM, program=0, min_duration=5.0,
                       rng=random.Random(0))
        directives = [l for l in out.splitlines()
                      if l.startswith("%%MIDI program")]
        self.assertEqual(len(directives), 1)


class TestCommonRejections(unittest.TestCase):
    def test_invalid_mode_rejected(self):
        with self.assertRaises(AssignmentError) as cm:
            annotate(SIMPLE, "loud")
        self.assertIn("mode must be one of", str(cm.exception))

    def test_non_string_text_rejected(self):
        with self.assertRaises(AssignmentError) as cm:
            annotate(123, FIXED, program=0)  # type: ignore[arg-type]
        self.assertIn("must be a string", str(cm.exception))

    def test_unsupported_abc_propagates(self):
        # The parser (#163) rejects chords; annotate must surface that.
        with self.assertRaises(Exception):
            annotate("X:1\nK:C\n[CEG]\n", FIXED, program=0)


class TestDurationParser(unittest.TestCase):
    """Exercise duration interpretation through the random filter."""

    def _directive_count(self, body: str, min_duration: float) -> int:
        src = f"X:1\nK:C\n{body}\n"
        out = annotate(src, RANDOM, program=0,
                       min_duration=min_duration, rng=random.Random(0))
        return sum(1 for l in out.splitlines()
                   if l.startswith("%%MIDI program"))

    def test_integer(self):
        self.assertEqual(self._directive_count("C2 D2", 2.0), 2)
        self.assertEqual(self._directive_count("C2 D2", 3.0), 1)

    def test_slash_alone_means_half(self):
        self.assertEqual(self._directive_count("C/ D/", 0.5), 2)
        self.assertEqual(self._directive_count("C/ D/", 0.6), 1)

    def test_n_slash_means_half_n(self):
        self.assertEqual(self._directive_count("C3/ D3/", 1.5), 2)
        self.assertEqual(self._directive_count("C3/ D3/", 2.0), 1)

    def test_slash_n_means_one_over_n(self):
        # "/2" = 0.5
        self.assertEqual(self._directive_count("C/2 D/2", 0.5), 2)
        self.assertEqual(self._directive_count("C/2 D/2", 0.6), 1)


if __name__ == "__main__":
    unittest.main()
