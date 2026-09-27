"""Smoke + end-to-end tests for miau_dio.cli -- stdlib unittest only.

Parser shape is verified through argparse's subparser action without
invoking handlers. End-to-end invocations run the real handlers with
XDG_DATA_HOME pointed at a TemporaryDirectory and store's module-level
DATA/INDEX rebound to the same tmpdir, so nothing escapes to the user's
real data directory. No audio is invoked.
"""
import argparse
import contextlib
import io
import json
import os
import pathlib
import tempfile
import unittest

from miau_dio import cli
from miau_dio.store import store


def _subparsers(parser: argparse.ArgumentParser):
    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            return a.choices
    return {}


class _CliCase(unittest.TestCase):
    """Isolate XDG_DATA_HOME and store.DATA/INDEX per test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._prev_xdg = os.environ.get("XDG_DATA_HOME")
        os.environ["XDG_DATA_HOME"] = self._tmp.name

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
        if self._prev_xdg is None:
            os.environ.pop("XDG_DATA_HOME", None)
        else:
            os.environ["XDG_DATA_HOME"] = self._prev_xdg
        self._tmp.cleanup()

    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main(argv)
        return buf.getvalue()

    def _write_abc(self, body="X:1\nK:C\nC D E F|\n", name="src.abc"):
        p = pathlib.Path(self._tmp.name) / name
        p.write_text(body)
        return str(p)


class TestParserShape(unittest.TestCase):
    def test_top_level_groups(self):
        subs = _subparsers(cli.build_parser())
        self.assertEqual(
            set(subs.keys()),
            {"idea", "instr", "family", "play", "config", "backend"},
        )

    def test_idea_subcommands(self):
        subs = _subparsers(cli.build_parser()._subparsers._group_actions[0]
                           .choices["idea"])
        self.assertEqual(
            set(subs.keys()),
            {"new", "add", "list", "show", "edit", "rename", "dup",
             "tag", "note", "assign", "rm"},
        )

    def test_instr_subcommands(self):
        p = cli.build_parser()
        idea_group = p._subparsers._group_actions[0].choices
        instr = idea_group["instr"]
        self.assertEqual(
            set(_subparsers(instr).keys()),
            {"add", "list", "show", "dup", "rename", "rm"},
        )

    def test_play_subcommands(self):
        p = cli.build_parser()
        play = p._subparsers._group_actions[0].choices["play"]
        self.assertEqual(set(_subparsers(play).keys()), {"file", "idea"})

    def test_backend_subcommands(self):
        p = cli.build_parser()
        be = p._subparsers._group_actions[0].choices["backend"]
        self.assertEqual(
            set(_subparsers(be).keys()),
            {"setup", "status", "selftest"},
        )

    def test_family_only_list(self):
        p = cli.build_parser()
        fam = p._subparsers._group_actions[0].choices["family"]
        self.assertEqual(set(_subparsers(fam).keys()), {"list"})

    def test_every_parser_formats_help(self):
        """format_help() must not raise on any node of the tree."""
        def walk(parser):
            parser.format_help()
            for child in _subparsers(parser).values():
                walk(child)
        walk(cli.build_parser())


class TestInstr(_CliCase):
    def test_add_and_show(self):
        out = self._run(["instr", "add", "piano", "0"])
        self.assertIn("Added instrument: piano", out)
        show = self._run(["instr", "show", "piano"])
        self.assertIn("name:    piano", show)
        self.assertIn("program: 0", show)

    def test_add_with_family(self):
        self._run(["instr", "add", "cello", "42", "--family", "strings"])
        show = self._run(["instr", "show", "cello"])
        self.assertIn("family:  strings", show)

    def test_add_out_of_range_exits(self):
        with self.assertRaises(SystemExit) as cm:
            self._run(["instr", "add", "bad", "200"])
        self.assertIn("out of GM range", str(cm.exception))

    def test_add_duplicate_exits(self):
        self._run(["instr", "add", "piano", "0"])
        with self.assertRaises(SystemExit) as cm:
            self._run(["instr", "add", "piano", "1"])
        self.assertIn("already exists", str(cm.exception))

    def test_list_empty(self):
        self.assertEqual(self._run(["instr", "list"]), "")

    def test_list_shows_added(self):
        self._run(["instr", "add", "piano", "0"])
        out = self._run(["instr", "list"])
        self.assertIn("piano  program=0", out)

    def test_list_json_is_valid(self):
        self._run(["instr", "add", "piano", "0", "--family", "keys"])
        out = self._run(["instr", "list", "--json"])
        data = json.loads(out)
        self.assertEqual(data, [{"name": "piano", "program": 0,
                                 "family": "keys"}])

    def test_rename(self):
        self._run(["instr", "add", "piano", "0"])
        out = self._run(["instr", "rename", "piano", "grand"])
        self.assertIn("Renamed: piano -> grand", out)

    def test_rm_with_yes(self):
        self._run(["instr", "add", "piano", "0"])
        out = self._run(["instr", "rm", "piano", "-y"])
        self.assertIn("Deleted.", out)
        self.assertEqual(self._run(["instr", "list"]), "")

    def test_dup(self):
        self._run(["instr", "add", "piano", "0"])
        out = self._run(["instr", "dup", "piano", "--name", "piano2"])
        self.assertIn("Duplicated: piano2", out)


class TestFamily(_CliCase):
    def test_empty(self):
        self.assertEqual(self._run(["family", "list"]).strip(), "-")

    def test_distinct_sorted(self):
        self._run(["instr", "add", "piano", "0", "--family", "keys"])
        self._run(["instr", "add", "cello", "42", "--family", "strings"])
        out = self._run(["family", "list"])
        self.assertEqual(out.splitlines(), ["keys", "strings"])


class TestIdea(_CliCase):
    def test_add_and_list(self):
        abc = self._write_abc()
        out = self._run(["idea", "add", "demo", abc])
        self.assertIn("Saved", out)
        listing = self._run(["idea", "list"])
        self.assertIn("demo", listing)

    def test_show(self):
        abc = self._write_abc()
        self._run(["idea", "add", "demo", abc])
        idea_id = store.all_ideas()[0].id
        out = self._run(["idea", "show", idea_id])
        self.assertIn("[", out)
        self.assertIn("demo", out)

    def test_assign_writes_program(self):
        abc = self._write_abc()
        self._run(["idea", "add", "demo", abc])
        idea_id = store.all_ideas()[0].id
        out = self._run(["idea", "assign", idea_id, "--program", "40"])
        self.assertIn("program 40", out)
        text = store.abc_path(idea_id).read_text()
        self.assertIn("%%MIDI program 40", text)

    def test_assign_at_writes_single_directive(self):
        abc = self._write_abc()
        self._run(["idea", "add", "demo", abc])
        idea_id = store.all_ideas()[0].id
        self._run(["idea", "assign", idea_id, "--program", "0", "--at", "2"])
        text = store.abc_path(idea_id).read_text()
        directives = [l for l in text.splitlines()
                      if l.startswith("%%MIDI program")]
        self.assertEqual(directives, ["%%MIDI program 0"])

    def test_assign_missing_idea_exits(self):
        with self.assertRaises(Exception):
            self._run(["idea", "assign", "deadbeef", "--program", "0"])

    def test_assign_out_of_range_exits(self):
        abc = self._write_abc()
        self._run(["idea", "add", "demo", abc])
        idea_id = store.all_ideas()[0].id
        with self.assertRaises(SystemExit) as cm:
            self._run(["idea", "assign", idea_id, "--program", "200"])
        self.assertIn("out of GM range", str(cm.exception))

    def test_list_json_is_valid(self):
        abc = self._write_abc()
        self._run(["idea", "add", "demo", abc, "-t", "wip"])
        out = self._run(["idea", "list", "--json"])
        data = json.loads(out)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "demo")
        self.assertIn("wip", data[0]["tags"])


class TestPlayGuards(_CliCase):
    def test_random_with_empty_library_exits(self):
        abc = self._write_abc()
        self._run(["idea", "add", "demo", abc])
        idea_id = store.all_ideas()[0].id
        with self.assertRaises(SystemExit) as cm:
            self._run(["play", "idea", idea_id, "--random", "--silent"])
        self.assertIn("library is empty", str(cm.exception))


class TestConfig(_CliCase):
    def test_show_defaults(self):
        out = self._run(["config", "show"])
        self.assertIn("key:", out)
        self.assertIn("bpm:", out)

    def test_set_and_show(self):
        out = self._run(["config", "set", "bpm", "100"])
        self.assertIn("bpm = 100", out)
        show = self._run(["config", "show"])
        self.assertIn("bpm: 100", show)

    def test_set_unknown_field_exits(self):
        with self.assertRaises(KeyError):
            self._run(["config", "set", "nope", "x"])


class TestBackend(_CliCase):
    def test_status_lists_backends(self):
        out = self._run(["backend", "status"])
        for name in ("abcmidi", "timidity", "sox"):
            self.assertIn(name, out)


if __name__ == "__main__":
    unittest.main()
