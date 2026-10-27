"""Tests for non-overlapping dubbing playback/export timing."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend import subs


class VoiceTimelineTests(unittest.TestCase):
    def test_short_overrun_fits_with_gentle_tempo_change(self):
        clips = [
            {"audio": "one.mp3", "start": 0.0, "end": 1.0},
            {"audio": "two.mp3", "start": 2.0, "end": 3.0},
        ]
        durations = {"one.mp3": 2.0, "two.mp3": 0.5}
        scheduled = subs.schedule_voice_clips(
            clips, duration_probe=lambda path: durations[path.name]
        )
        self.assertAlmostEqual(scheduled[0]["start"], 0.0)
        self.assertGreater(scheduled[0]["_tempo"], 1.0)
        self.assertLessEqual(scheduled[0]["_tempo"], subs.MAX_VOICE_SPEED)
        self.assertAlmostEqual(scheduled[0]["_trim"], 1.97)
        self.assertAlmostEqual(scheduled[1]["start"], 2.0)

    def test_long_overrun_moves_next_clip_without_cutting_or_overlap(self):
        clips = [
            {"audio": "one.mp3", "start": 0.0, "end": 1.0},
            {"audio": "two.mp3", "start": 1.0, "end": 2.0},
            {"audio": "three.mp3", "start": 4.0, "end": 5.0},
        ]
        durations = {"one.mp3": 3.0, "two.mp3": 2.0, "three.mp3": 0.5}
        scheduled = subs.schedule_voice_clips(
            clips, duration_probe=lambda path: durations[path.name]
        )
        self.assertAlmostEqual(scheduled[0]["_tempo"], 1.0)
        self.assertAlmostEqual(scheduled[1]["start"], 3.0)
        self.assertAlmostEqual(scheduled[2]["start"], 5.0)
        for previous, current in zip(scheduled, scheduled[1:]):
            previous_end = previous["start"] + (
                previous["_trim"] if previous["_trim"] is not None
                else durations[pathlib.Path(previous["audio"]).name]
            )
            self.assertLessEqual(previous_end, current["start"] + 1e-9)

    def test_schedule_is_sorted_by_timeline_start(self):
        clips = [
            {"audio": "later.mp3", "start": 2.0, "end": 3.0},
            {"audio": "earlier.mp3", "start": 0.0, "end": 1.0},
        ]
        scheduled = subs.schedule_voice_clips(
            clips, duration_probe=lambda _path: 0.5
        )
        self.assertEqual([clip["audio"] for clip in scheduled], ["earlier.mp3", "later.mp3"])

    def test_voice_filter_applies_tempo_trim_and_scheduled_delay(self):
        clip = {"start": 2.0, "_tempo": 1.1, "_trim": 1.5}
        self.assertEqual(
            subs._voice_filter(1, clip, 0),
            "[1:a]asetpts=PTS-STARTPTS,atempo=1.100000,atrim=duration=1.500,adelay=2000:all=1[a0]",
        )


if __name__ == "__main__":
    unittest.main()
