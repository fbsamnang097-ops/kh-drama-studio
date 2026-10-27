"""Regression test for bulk Character voice assignment and stale-audio invalidation."""

import tempfile
import unittest

from backend import registry as RG


class ApplyAllVoiceTest(unittest.TestCase):
    def test_apply_one_voice_to_all_characters_and_clear_changed_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            con = RG.connect(directory)
            try:
                project = "apply-all-test"
                RG.ensure_project(con, project)
                chars = [
                    {"id": "male-1", "name": "តួប្រុស", "gender": "male", "age": "adult",
                     "role": "male", "voice": "male_adult_1", "named": True},
                    {"id": "female-1", "name": "តួស្រី", "gender": "female", "age": "adult",
                     "role": "female", "voice": "female_adult_1", "named": True},
                ]
                for char in chars:
                    RG.upsert_character(con, project, char, keep_voice=False)
                RG.save_segments(con, project, [
                    {"idx": 0, "cid": "male-1", "voice_id": "male_adult_1", "start": 0, "end": 1,
                     "zh": "A", "km": "ក", "audio": "/files/male.mp3"},
                    {"idx": 1, "cid": "female-1", "voice_id": "female_adult_1", "start": 1, "end": 2,
                     "zh": "B", "km": "ខ", "audio": "/files/female.mp3"},
                ])

                chosen_voice = "male_adult_1"
                current = {c["id"]: c for c in RG.characters(con, project)}
                changed = []
                for cid in ("male-1", "female-1"):
                    if current[cid]["voice"] != chosen_voice:
                        changed.append(cid)
                    RG.set_voice(con, cid, chosen_voice, manual=True)
                rows = [{"idx": s["idx"], "cid": s["cid"], "voice_id": chosen_voice,
                         "start": s["start"], "end": s["end"], "zh": s["zh"]}
                        for s in RG.segments(con, project)]
                RG.save_segments(con, project, rows)
                RG.clear_character_segment_audio(con, project, changed)

                assigned = RG.characters(con, project)
                self.assertEqual({c["voice"] for c in assigned}, {chosen_voice})
                self.assertTrue(all(c["manual"] for c in assigned))
                saved_segments = {s["cid"]: s for s in RG.segments(con, project)}
                self.assertEqual(saved_segments["male-1"]["audio"], "/files/male.mp3")
                self.assertIsNone(saved_segments["female-1"]["audio"])
                self.assertEqual({s["voice_id"] for s in saved_segments.values()}, {chosen_voice})
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()
