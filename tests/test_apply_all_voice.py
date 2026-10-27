"""Regression test for bulk Character voice assignment and stale-audio invalidation."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import identity as ID
from backend import registry as RG


class ApplyAllVoiceTest(unittest.TestCase):
    def test_resolver_namespaces_narrators_across_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            con = RG.connect(directory)
            try:
                results = [
                    ID.resolve([{"zh": "旁白：他终于回到了家。", "start": 0, "end": 1}],
                               con=con, pid=project, provider="edge")
                    for project in ("first-project", "second-project")
                ]
                first_id = results[0]["characters"][0]["id"]
                second_id = results[1]["characters"][0]["id"]
                self.assertEqual(first_id, "narrator")
                self.assertNotEqual(second_id, first_id)
                self.assertTrue(second_id.startswith("narrator_"))
                self.assertEqual([c["id"] for c in RG.characters(con, "first-project")], [first_id])
                self.assertEqual([c["id"] for c in RG.characters(con, "second-project")], [second_id])
            finally:
                con.close()

    def test_narrator_ids_are_project_scoped_and_legacy_cast_can_be_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            con = RG.connect(directory)
            try:
                first, second = "first-project", "second-project"
                RG.ensure_project(con, first)
                RG.ensure_project(con, second)
                narrator = {"id": "narrator", "name": "អ្នកនិទាន", "gender": "male",
                            "age": "adult", "role": "旁白", "voice": "male_adult_1",
                            "kind": "narrator", "named": False}
                RG.ensure_project_character(con, first, narrator)
                RG.save_segments(con, second, [{"idx": 0, "cid": "narrator", "voice_id": "male_adult_1",
                                                "start": 0, "end": 1, "zh": "A", "km": "ក"}])

                restored_id = RG.ensure_project_character(con, second, narrator)
                self.assertNotEqual(restored_id, "narrator")
                self.assertTrue(restored_id.startswith("narrator_"))
                self.assertEqual([c["id"] for c in RG.characters(con, first)], ["narrator"])
                self.assertEqual([c["id"] for c in RG.characters(con, second)], [restored_id])
                self.assertEqual(RG.segments(con, second)[0]["cid"], restored_id)
                self.assertEqual(RG.project_character_id(con, second, "narrator"), restored_id)
                with self.assertRaises(ValueError):
                    RG.upsert_character(con, second, narrator)
            finally:
                con.close()

    def test_apply_all_recovers_legacy_narrator_missing_from_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store, data = root / "store", root / "data"
            store.mkdir()
            data.mkdir()
            con = RG.connect(data)
            try:
                RG.ensure_project(con, "older-project")
                RG.ensure_project(con, "current-project")
                narrator = {"id": "narrator", "name": "អ្នកនិទាន", "gender": "male",
                            "age": "adult", "role": "旁白", "voice": "male_adult_1",
                            "kind": "narrator", "named": False}
                RG.ensure_project_character(con, "older-project", narrator)
                RG.save_segments(con, "current-project", [{
                    "idx": 0, "cid": "narrator", "voice_id": "male_adult_1",
                    "start": 0, "end": 1, "zh": "A", "km": "ក", "audio": "/files/old.mp3",
                }])
            finally:
                con.close()
            (store / "current-project.cast.json").write_text(
                json.dumps({"characters": [narrator], "items": [{"char_id": "narrator"}]}, ensure_ascii=False),
                encoding="utf-8",
            )

            from backend import main as API
            with patch.object(API, "STORE", store), patch.object(API, "reg", side_effect=lambda: RG.connect(data)):
                result = API.characters_assign(API.AssignIn(
                    id="current-project", project="current-project",
                    overrides={"narrator": "female_adult_1"},
                ))

            restored_id = result["id_map"]["narrator"]
            self.assertTrue(restored_id.startswith("narrator_"))
            self.assertEqual(result["characters"][0]["id"], restored_id)
            self.assertEqual(result["characters"][0]["voice"], "female_adult_1")
            con = RG.connect(data)
            try:
                self.assertEqual(RG.segments(con, "current-project")[0]["cid"], restored_id)
                self.assertIsNone(RG.segments(con, "current-project")[0]["audio"])
                self.assertEqual([c["id"] for c in RG.characters(con, "older-project")], ["narrator"])
            finally:
                con.close()

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
