"""Tests for miau_dio.platform.platform -- stdlib unittest only."""
import unittest
from unittest import mock

from miau_dio.platform import platform as p


class TestOpenUrl(unittest.TestCase):
    def test_rejects_empty(self):
        with self.assertRaises(RuntimeError):
            p.open_url("")

    def test_rejects_non_string(self):
        with self.assertRaises(RuntimeError):
            p.open_url(None)

    def test_uses_termux_open_url_when_available(self):
        with mock.patch.object(p.shutil, "which",
                               return_value="/usr/bin/termux-open-url"):
            with mock.patch.object(p.subprocess, "run") as m:
                p.open_url("https://example.com/")
        m.assert_called_once()
        args, _ = m.call_args
        self.assertEqual(args[0][0], "/usr/bin/termux-open-url")
        self.assertEqual(args[0][1], "https://example.com/")

    def test_falls_back_to_webbrowser(self):
        with mock.patch.object(p.shutil, "which", return_value=None):
            with mock.patch.object(p.webbrowser, "open",
                                   return_value=True) as m:
                p.open_url("https://example.com/")
        m.assert_called_once_with("https://example.com/")

    def test_raises_when_no_browser(self):
        with mock.patch.object(p.shutil, "which", return_value=None):
            with mock.patch.object(p.webbrowser, "open", return_value=False):
                with self.assertRaises(RuntimeError):
                    p.open_url("https://example.com/")




class TestAudioPlayer(unittest.TestCase):
    def test_prefers_mpv(self):
        with mock.patch.object(p.shutil, "which",
                               side_effect=lambda x: x if x == "mpv" else None):
            self.assertEqual(p.audio_player()[0], "mpv")

    def test_falls_back_to_termux_media_player(self):
        with mock.patch.object(p.shutil, "which",
                               side_effect=lambda x: x if x == "termux-media-player" else None):
            self.assertEqual(p.audio_player()[0], "termux-media-player")

    def test_falls_back_to_sox_play(self):
        with mock.patch.object(p.shutil, "which",
                               side_effect=lambda x: x if x == "play" else None):
            self.assertEqual(p.audio_player()[0], "play")

    def test_falls_back_to_aplay(self):
        with mock.patch.object(p.shutil, "which",
                               side_effect=lambda x: x if x == "aplay" else None):
            self.assertEqual(p.audio_player()[0], "aplay")

    def test_raises_when_none_available(self):
        with mock.patch.object(p.shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError) as cm:
                p.audio_player()
        self.assertIn("termux-api", str(cm.exception))
if __name__ == "__main__":
    unittest.main()
