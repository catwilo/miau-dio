"""Tests for the Project/Track domain model (task #171) -- stdlib unittest."""
import unittest

from miau_dio.project.model import Project, ProjectError, Track


class TestTrack(unittest.TestCase):
    def test_minimal(self):
        t = Track(name="bass", type="midi")
        self.assertEqual(t.name, "bass")
        self.assertEqual(t.type, "midi")
        self.assertEqual(t.instrument, "")
        self.assertEqual(t.content, "")
        self.assertEqual(t.timing, "")
        self.assertEqual(t.volume, 1.0)
        self.assertEqual(t.pan, 0.0)
        self.assertEqual(t.effects, [])

    def test_full(self):
        t = Track(
            name="lead", type="midi", instrument="Square Lead",
            content="C4 E4 G4", timing="1:0:0",
            volume=0.8, pan=-0.3, effects=["reverb", "delay"],
        )
        self.assertEqual(t.instrument, "Square Lead")
        self.assertEqual(t.effects, ["reverb", "delay"])

    def test_name_required(self):
        with self.assertRaises(ProjectError):
            Track(name="", type="midi")

    def test_type_required(self):
        with self.assertRaises(ProjectError):
            Track(name="bass", type="")

    def test_name_stripped(self):
        self.assertEqual(Track(name="  bass  ", type="midi").name, "bass")

    def test_volume_range(self):
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", volume=3.0)
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", volume=-1.0)

    def test_pan_range(self):
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", pan=2.0)
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", pan=-2.0)

    def test_content_must_be_str(self):
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", content=123)

    def test_effects_must_be_list(self):
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", effects="reverb")

    def test_bool_is_not_a_number(self):
        with self.assertRaises(ProjectError):
            Track(name="bass", type="midi", volume=True)

    def test_roundtrip(self):
        t = Track(name="bass", type="midi", content="C E G",
                  volume=0.7, pan=0.2, effects=["eq"])
        self.assertEqual(Track.from_dict(t.to_dict()), t)

    def test_from_dict_missing_field(self):
        with self.assertRaises(ProjectError):
            Track.from_dict({"name": "bass"})


class TestProject(unittest.TestCase):
    def test_minimal(self):
        p = Project(name="demo")
        self.assertEqual(p.name, "demo")
        self.assertEqual(p.tracks, [])
        self.assertEqual(p.tempo, 120.0)
        self.assertEqual(p.time_signature, "4/4")
        self.assertEqual(p.key, "C")

    def test_full(self):
        p = Project(
            name="demo",
            tracks=[Track(name="bass", type="midi")],
            tempo=95.0, time_signature="3/4", key="Am",
        )
        self.assertEqual(p.tempo, 95.0)
        self.assertEqual(p.time_signature, "3/4")
        self.assertEqual(p.key, "Am")
        self.assertEqual(len(p.tracks), 1)

    def test_name_required(self):
        with self.assertRaises(ProjectError):
            Project(name="")

    def test_tempo_range(self):
        with self.assertRaises(ProjectError):
            Project(name="demo", tempo=10.0)
        with self.assertRaises(ProjectError):
            Project(name="demo", tempo=500.0)

    def test_time_signature_format(self):
        with self.assertRaises(ProjectError):
            Project(name="demo", time_signature="4-4")
        with self.assertRaises(ProjectError):
            Project(name="demo", time_signature="0/4")
        with self.assertRaises(ProjectError):
            Project(name="demo", time_signature="4/0")

    def test_time_signature_normalized(self):
        p = Project(name="demo", time_signature="  6/8  ")
        self.assertEqual(p.time_signature, "6/8")

    def test_tracks_must_be_track_instances(self):
        with self.assertRaises(ProjectError):
            Project(name="demo", tracks=["bass"])

    def test_roundtrip(self):
        p = Project(
            name="demo",
            tracks=[
                Track(name="bass", type="midi", content="C E G"),
                Track(name="drum", type="pattern", content="bd sd hh"),
            ],
            tempo=90.0, time_signature="6/8", key="Dm",
            created="2026-01-01T00:00:00",
            modified="2026-01-01T00:00:00",
        )
        self.assertEqual(Project.from_dict(p.to_dict()), p)

    def test_from_dict_missing_name(self):
        with self.assertRaises(ProjectError):
            Project.from_dict({"tempo": 120})


if __name__ == "__main__":
    unittest.main()
