"""Acceptance Tests A–J: character detection & automatic voice assignment.

បង្កើតវីដេអូសាកល្បងជាមួយសំឡេងពិត (F0 ខុសៗគ្នា) រួចរត់ pipeline ពិត៖
  ffmpeg audio → diarize (F0) → identity (fusion) → voices (assignment)

រត់:  python tests/test_characters.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import diarize as D          # noqa: E402
from backend import identity as ID       # noqa: E402
from backend import voices as V          # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"   [{detail}]" if detail else ""))


def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *a],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])


def make_video(path, speakers):
    """speakers: [(start, end, f0)] → mp4 ដែលមានសំឡេង F0 ខុសៗគ្នាតាមចន្លោះ"""
    work = tempfile.mkdtemp()
    parts, lst = [], os.path.join(work, "l.txt")
    for i, (a, b, f0) in enumerate(speakers):
        p = os.path.join(work, f"s{i}.wav")
        ff("-f", "lavfi", "-i", f"sine=frequency={f0}:duration={b - a},volume=0.35",
           "-af", "tremolo=f=4:d=0.9", "-ar", "16000", "-ac", "1", p)
        parts.append(p)
    with open(lst, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    wav = os.path.join(work, "all.wav")
    ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", wav)
    total = speakers[-1][1]
    ff("-f", "lavfi", "-i", f"color=c=navy:s=320x568:r=12:d={total}", "-i", wav,
       "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", path)
    shutil.rmtree(work, ignore_errors=True)
    return path


def run_case(tmp, name, lines, speakers, book=None):
    video = make_video(os.path.join(tmp, f"{name}.mp4"), speakers)
    audio = D.analyze_segments(video, lines)
    return ID.resolve(lines, audio, video_id=name, voicebook=book or {})


def main():
    tmp = tempfile.mkdtemp()
    print("\n=== Test A: one adult male ===")
    lines = [{"start": 0, "end": 2, "zh": "「我回来了。」"}]
    r = run_case(tmp, "A", lines, [(0, 2, 110)])
    c = r["characters"][0]
    check("A: voice is adult male", V.info(c["voice"])["gender"] == "male" and V.info(c["voice"])["age"] == "adult",
          f"{c['gender']}/{c['age']} → {c['voice']}")

    print("\n=== Test B: one adult female ===")
    r = run_case(tmp, "B", [{"start": 0, "end": 2, "zh": "「你是谁？」"}], [(0, 2, 210)])
    c = r["characters"][0]
    check("B: voice is adult female", V.info(c["voice"])["gender"] == "female" and V.info(c["voice"])["age"] == "adult",
          f"{c['gender']}/{c['age']} → {c['voice']}")

    print("\n=== Test C: elderly man ===")
    r = run_case(tmp, "C", [{"start": 0, "end": 2, "zh": "爷爷说：「孩子，别怕。」"}], [(0, 2, 105)])
    c = r["characters"][0]
    check("C: elderly male voice", V.info(c["voice"])["gender"] == "male" and V.info(c["voice"])["age"] == "elderly",
          f"{c['gender']}/{c['age']} → {c['voice']}")

    print("\n=== Test D: elderly woman ===")
    r = run_case(tmp, "D", [{"start": 0, "end": 2, "zh": "奶奶说：「吃饭了。」"}], [(0, 2, 190)])
    c = r["characters"][0]
    check("D: elderly female voice", V.info(c["voice"])["gender"] == "female" and V.info(c["voice"])["age"] == "elderly",
          f"{c['gender']}/{c['age']} → {c['voice']}")

    print("\n=== Test E: child ===")
    r = run_case(tmp, "E", [{"start": 0, "end": 2, "zh": "小孩说：「妈妈！」"}], [(0, 2, 330)])
    c = r["characters"][0]
    check("E: child voice", V.info(c["voice"])["age"] == "child", f"{c['gender']}/{c['age']} → {c['voice']}")

    print("\n=== Test F: scene with only male speakers ===")
    lines = [{"start": 0, "end": 2, "zh": "「你来了。」"},
             {"start": 2, "end": 4, "zh": "「坐吧。」"},
             {"start": 4, "end": 6, "zh": "「喝一杯。」"}]
    r = run_case(tmp, "F", lines, [(0, 2, 108), (2, 4, 128), (4, 6, 112)])
    genders = {V.info(c["voice"])["gender"] for c in r["characters"]}
    check("F: no female voice invented", genders == {"male"}, f"genders={genders}")

    print("\n=== Test G: mixed male + female scene ===")
    lines = [{"start": 0, "end": 2, "zh": "「你回来了。」"},        # 108 male
             {"start": 2, "end": 4, "zh": "「妈，我回来了。」"},     # 210 female
             {"start": 4, "end": 6, "zh": "「饭在锅里。」"},        # 108 male
             {"start": 6, "end": 8, "zh": "「谢谢妈。」"}]          # 210 female
    r = run_case(tmp, "G", lines, [(0, 2, 108), (2, 4, 210), (4, 6, 108), (6, 8, 210)])
    by_id = {c["id"]: V.info(c["voice"]) for c in r["characters"]}
    seq = [by_id[i["char_id"]]["gender"] for i in r["items"]]
    check("G: each segment uses its own speaker's gender", seq == ["male", "female", "male", "female"], str(seq))
    check("G: exactly two characters", len(r["characters"]) == 2, str([c["name"] for c in r["characters"]]))

    print("\n=== Test H: same character in several scenes ===")
    lines = [{"start": 0, "end": 2, "zh": "「走吧。」"},        # 112 male
             {"start": 2, "end": 4, "zh": "「好。」"},          # 212 female
             {"start": 4, "end": 6, "zh": "「等等我。」"},      # 112 male (same speaker again)
             {"start": 6, "end": 8, "zh": "「快来。」"}]        # 212 female
    r = run_case(tmp, "H", lines, [(0, 2, 112), (2, 4, 212), (4, 6, 112), (6, 8, 212)])
    voices_by_id = {c["id"]: c["voice"] for c in r["characters"]}
    used = [voices_by_id[i["char_id"]] for i in r["items"]]
    check("H: same speaker keeps the same voice (lines 1 & 3)", used[0] == used[2], f"{used[0]} vs {used[2]}")
    check("H: female keeps her voice (lines 2 & 4)", used[1] == used[3], f"{used[1]} vs {used[3]}")

    print("\n=== Test I: two different male characters ===")
    lines = [{"start": 0, "end": 2, "zh": "「我是小明。」"},
             {"start": 2, "end": 2, "zh": "「我是老王。」"},
             {"start": 2, "end": 4, "zh": "「你好。」"},
             {"start": 4, "end": 6, "zh": "「你好啊。」"}]
    speakers = [(0, 2, 108), (2, 4, 132), (4, 6, 108)]
    lines = [lines[0], lines[2], lines[3]]
    r = run_case(tmp, "I", lines, speakers)
    vs = [c["voice"] for c in r["characters"] if c["kind"] == "character"]
    check("I: two males get distinct voices", len(vs) >= 2 and len(set(vs)) == len(vs), str(vs))
    check("I: both are male", all(V.info(v)["gender"] == "male" for v in vs), str(vs))

    print("\n=== Test J: uncertain speaker ===")
    # គ្មានសំឡេង (video ស្ងាត់) + អត្ថបទគ្មានភេទ/អាយុ → unknown
    silent = os.path.join(tmp, "J.mp4")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=160x284:r=8:d=4", "-c:v", "libx264",
                    "-preset", "ultrafast", "-pix_fmt", "yuv420p", silent], check=True)
    jlines = [{"start": 0, "end": 2, "zh": "「嗯。」"}, {"start": 2, "end": 4, "zh": "「哦。」"}]
    audio = D.analyze_segments(silent, jlines)
    r = ID.resolve(jlines, audio, video_id="J")
    c = r["characters"][0]
    check("J: does not invent gender", c["gender"] == "unknown", f"{c['gender']}/{c['age']}")
    check("J: uses the neutral fallback voice", c["voice"] == "unknown_1", c["voice"])

    print("\n=== Extra: voice book keeps a name's voice across episodes ===")
    book = {}
    r1 = run_case(tmp, "X1", [{"start": 0, "end": 2, "zh": "小明说：「你好。」"}], [(0, 2, 108)], book=book)
    v1 = [c for c in r1["characters"] if c.get("named")][0]
    book[v1["name"]] = v1["voice"]
    # ភាគ ២៖ សំឡេងខុសគ្នាបន្តិច (ឧ. អ្នកសម្តែងខុស) តែឈ្មោះដដែល → ត្រូវរក្សាសំឡេងដដែល
    r2 = run_case(tmp, "X2", [{"start": 0, "end": 2, "zh": "小明说：「再见。」"}], [(0, 2, 118)], book=book)
    v2 = [c for c in r2["characters"] if c.get("named")][0]
    check("voicebook: same name keeps the same voice", v1["voice"] == v2["voice"], f"{v1['voice']} → {v2['voice']}")

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'=' * 52}\n{PASS.__len__()} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
        return 1
    print("ALL ACCEPTANCE TESTS PASSED ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
