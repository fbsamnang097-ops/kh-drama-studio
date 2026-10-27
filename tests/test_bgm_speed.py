"""Regression checks for bounded, faster BGM vocal removal."""
import unittest

from backend import main as API


class BgmSpeedTests(unittest.TestCase):
    def test_processing_deadline_stays_below_two_minutes(self):
        self.assertLess(API.BGM_MAX_SECONDS, 120)

    def test_demucs_runs_without_slow_tta_and_with_reduced_overlap(self):
        command = API._demucs_command("htdemucs", "input.wav", "separator")
        self.assertIn("--shifts", command)
        self.assertEqual(command[command.index("--shifts") + 1], "0")
        self.assertEqual(command[command.index("--overlap") + 1], "0.1")
        self.assertIn("--two-stems=vocals", command)

    def test_timeout_fallback_uses_stereo_center_cancel_or_mono_voice_band_cut(self):
        stereo = API._quick_bgm_filter(2)
        mono = API._quick_bgm_filter(1)
        self.assertIn("FL-0.5*FR", stereo)
        self.assertIn("FR-0.5*FL", stereo)
        self.assertIn("equalizer", mono)
        self.assertNotEqual(stereo, mono)


if __name__ == "__main__":
    unittest.main()
