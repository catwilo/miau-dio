"""Tests for miau_dio.pipeline.pipeline -- stdlib unittest only.

The pipeline shells out to abc2midi and timidity. These tests replace
subprocess.run with a mock, so no external binary and no audio hardware
is needed; only the orchestration logic (argument construction, file
validation, soundfont selection, gain handling) is exercised.
"""
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

from miau_dio.pipeline import pipeline


class _PipelineCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.abc = pathlib.Path(self._tmp.name) / "song.abc"
        self.abc.write_text("X:1\nK:C\nC D E F|\n")
        self.out = pathlib.Path(self._tmp.name) / "out.wav"
        self.sf = pathlib.Path(self._tmp.name) / "fake.sf2"
        self.sf.write_bytes(b"RIFF")

    def tearDown(self):
        self._tmp.cleanup()

    def _run_ok(self, recorded):
        """Return a fake subprocess.run that records calls and succeeds."""
        def fake(cmd, **kwargs):
            recorded.append((cmd, kwargs))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return fake


class TestRenderMissingFile(_PipelineCase):
    def test_missing_abc_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            pipeline.render(str(self.abc.parent / "nope.abc"), str(self.out))


class TestRenderCalls(_PipelineCase):
    def test_calls_abc2midi_then_timidity(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=str(self.sf), gain=0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0][0], "abc2midi")
        self.assertEqual(calls[1][0][0], "timidity")

    def test_abc2midi_receives_input_and_output(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=str(self.sf), gain=0)
        cmd = calls[0][0]
        self.assertIn(str(self.abc), cmd)
        self.assertIn("-o", cmd)
        mid_path = cmd[cmd.index("-o") + 1]
        self.assertTrue(mid_path.endswith(".mid"))

    def test_timidity_receives_wav_output(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=str(self.sf), gain=0)
        cmd = calls[1][0]
        self.assertIn("-Ow", cmd)
        self.assertIn("-o", cmd)
        self.assertEqual(cmd[cmd.index("-o") + 1], str(self.out))


class TestSoundfont(_PipelineCase):
    def test_explicit_soundfont_used(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=str(self.sf), gain=0)
        cmd = calls[1][0]
        self.assertIn("-x", cmd)
        sf_spec = cmd[cmd.index("-x") + 1]
        self.assertEqual(sf_spec, f"soundfont {self.sf}")

    def test_missing_soundfont_omits_x_flag(self):
        calls = []
        missing = str(self.sf.parent / "missing.sf2")
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=missing, gain=0)
        cmd = calls[1][0]
        self.assertNotIn("-x", cmd)

    def test_default_soundfont_used_when_not_given(self):
        calls = []
        with mock.patch.object(pipeline, "soundfont_path",
                               return_value=self.sf):
            with mock.patch.object(pipeline.subprocess, "run",
                                   side_effect=self._run_ok(calls)):
                pipeline.render(str(self.abc), str(self.out), gain=0)
        cmd = calls[1][0]
        self.assertIn("-x", cmd)


class TestGain(_PipelineCase):
    def test_gain_zero_omits_volume(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=str(self.sf), gain=0)
        cmd = calls[1][0]
        self.assertFalse(any(a.startswith("--volume=") for a in cmd))

    def test_gain_applied_as_volume(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            pipeline.render(str(self.abc), str(self.out),
                            soundfont=str(self.sf), gain=6.0)
        cmd = calls[1][0]
        vol = [a for a in cmd if a.startswith("--volume=")]
        self.assertEqual(len(vol), 1)
        self.assertEqual(vol[0], "--volume=250")


class TestRunHelperFailure(_PipelineCase):
    def test_nonzero_returncode_raises_runtimeerror(self):
        def fake(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, "", "boom")
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=fake):
            with self.assertRaises(RuntimeError) as cm:
                pipeline.render(str(self.abc), str(self.out),
                                soundfont=str(self.sf))
        self.assertIn("abc2midi failed", str(cm.exception))
        self.assertIn("boom", str(cm.exception))


class TestReturnValue(_PipelineCase):
    def test_returns_out_path(self):
        calls = []
        with mock.patch.object(pipeline.subprocess, "run",
                               side_effect=self._run_ok(calls)):
            result = pipeline.render(str(self.abc), str(self.out),
                                     soundfont=str(self.sf))
        self.assertEqual(result, str(self.out))


if __name__ == "__main__":
    unittest.main()
