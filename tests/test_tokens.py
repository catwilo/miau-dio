"""Tests for miau_dio.abcparse.tokens -- stdlib unittest only."""
import unittest

from miau_dio.abcparse.tokens import (
    ABCParseError, Barline, Header, MidiProgram, Note, parse, tokens,
)


def _one_note(text: str) -> Note:
    s = parse(text)
    assert len(s.notes) == 1, f"expected 1 note, got {len(s.notes)}"
    return s.notes[0]


class TestHeaders(unittest.TestCase):
    def test_all_supported_headers(self):
        s = parse("X:1\nT:demo\nM:4/4\nL:1/4\nQ:1/4=120\nK:C\nC D E F|\n")
        keys = [h.key for h in s.headers]
        self.assertEqual(keys, ["X", "T", "M", "L", "Q", "K"])
        self.assertEqual(s.headers[0].value, "1")
        self.assertEqual(s.headers[4].value, "1/4=120")
        self.assertEqual(s.headers[5].value, "C")

    def test_unsupported_header_raises(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nV:1\nK:C\nC\n")
        self.assertIn("V:", str(cm.exception))

    def test_body_does_not_start_without_K(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nT:demo\nC D E\n")
        self.assertIn("K:", str(cm.exception))

    def test_empty_input_returns_empty_score(self):
        s = parse("")
        self.assertEqual(s.headers, [])
        self.assertEqual(s.notes, [])
        self.assertEqual(s.midi_programs, [])
        self.assertEqual(s.barlines, [])


class TestMidiProgram(unittest.TestCase):
    def test_simple_program(self):
        s = parse("X:1\nK:C\n%%MIDI program 40\nC\n")
        self.assertEqual(len(s.midi_programs), 1)
        self.assertEqual(s.midi_programs[0].program, 40)
        self.assertEqual(s.midi_programs[0].line, 3)

    def test_program_before_K(self):
        s = parse("X:1\n%%MIDI program 0\nK:C\nC\n")
        self.assertEqual(s.midi_programs[0].program, 0)

    def test_program_out_of_range_low(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n%%MIDI program -1\nC\n")
        self.assertIn("out of range", str(cm.exception))

    def test_program_out_of_range_high(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n%%MIDI program 128\nC\n")
        self.assertIn("out of range", str(cm.exception))

    def test_program_not_integer(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n%%MIDI program piano\nC\n")
        self.assertIn("integer", str(cm.exception))

    def test_unsupported_midi_directive_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n%%MIDI channel 1\nC\n")
        self.assertIn("only '%%MIDI program", str(cm.exception))


class TestNotes(unittest.TestCase):
    def test_pitch_range(self):
        s = parse("X:1\nK:C\nA B C D E F G a b c d e f g|\n")
        pitches = [n.pitch for n in s.notes]
        self.assertEqual(pitches, list("ABCDEFGabcdefg"))

    def test_accidentals(self):
        s = parse("X:1\nK:C\n^C _D =E ^^F __G|\n")
        accs = [(n.accidental, n.pitch) for n in s.notes]
        self.assertEqual(accs, [("^", "C"), ("_", "D"), ("=", "E"),
                                ("^^", "F"), ("__", "G")])

    def test_accidental_without_pitch_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n^ |\n")
        self.assertIn("not followed by a pitch letter", str(cm.exception))

    def test_octave_up(self):
        n = _one_note("X:1\nK:C\nc''\n")
        self.assertEqual(n.pitch, "c")
        self.assertEqual(n.octave, 2)

    def test_octave_down(self):
        n = _one_note("X:1\nK:C\nC,,\n")
        self.assertEqual(n.pitch, "C")
        self.assertEqual(n.octave, -2)

    def test_default_duration_is_one(self):
        n = _one_note("X:1\nK:C\nC\n")
        self.assertEqual(n.duration, "1")

    def test_duration_digits_and_slash(self):
        n = _one_note("X:1\nK:C\nC3/2\n")
        self.assertEqual(n.duration, "3/2")

    def test_positional_col_is_1_based(self):
        n = _one_note("X:1\nK:C\n  C\n")
        self.assertEqual(n.col, 3)
        self.assertEqual(n.line, 3)

    def test_comment_to_eol(self):
        s = parse("X:1\nK:C\nC D E % ignore F G A\n")
        self.assertEqual([n.pitch for n in s.notes], list("CDE"))


class TestBarlines(unittest.TestCase):
    def test_simple_barline(self):
        s = parse("X:1\nK:C\nC|\n")
        self.assertEqual([b.kind for b in s.barlines], ["|"])

    def test_double_barline(self):
        s = parse("X:1\nK:C\nC||\n")
        self.assertEqual([b.kind for b in s.barlines], ["||"])

    def test_final_barline(self):
        s = parse("X:1\nK:C\nC|]\n")
        self.assertEqual([b.kind for b in s.barlines], ["|]"])

    def test_barline_col_is_start_position(self):
        s = parse("X:1\nK:C\nCD|EF\n")
        self.assertEqual(s.barlines[0].col, 3)


class TestRejections(unittest.TestCase):
    def test_chord_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n[CEG]\n")
        self.assertIn("chords", str(cm.exception))

    def test_tuplet_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n(3CDE\n")
        self.assertIn("tuplets", str(cm.exception))

    def test_tie_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\nC-D\n")
        self.assertIn("ties", str(cm.exception))

    def test_decoration_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n!trill!C\n")
        self.assertIn("decorations", str(cm.exception))

    def test_grace_notes_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n{CD}C\n")
        self.assertIn("grace notes", str(cm.exception))

    def test_voice_overlay_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\nC&D\n")
        self.assertIn("voice overlay", str(cm.exception))

    def test_repeat_rejected(self):
        with self.assertRaises(ABCParseError) as cm:
            parse("X:1\nK:C\n|:C:|\n")
        self.assertIn("repeats", str(cm.exception))


class TestTokensFunction(unittest.TestCase):
    def test_flatten_is_source_ordered(self):
        s = "X:1\nK:C\n%%MIDI program 40\nC D|\n"
        kinds = [type(t).__name__ for t in tokens(s)]
        self.assertEqual(
            kinds,
            ["Header", "Header", "MidiProgram", "Note", "Note", "Barline"],
        )

    def test_flatten_returns_same_types(self):
        ts = tokens("X:1\nK:C\nC\n")
        self.assertIsInstance(ts[0], Header)
        self.assertIsInstance(ts[1], Header)
        self.assertIsInstance(ts[2], Note)


if __name__ == "__main__":
    unittest.main()
