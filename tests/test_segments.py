"""តេស្តបន្ទាត់វែង (long-line guard) — regression សម្រាប់ឃ្លា 5.3 → 41.0

រត់:  python tests/test_segments.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("PATH", os.path.dirname(shutil.which("ffmpeg") or "/usr/bin/ffmpeg") + ":" + os.environ.get("PATH", ""))

from backend import segments as SG   # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"   [{detail}]" if detail else ""))


def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *a],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])


def make_wav(path, parts, total=None):
    """parts: [(start, end, freq, volume)] → wav 16k mono (សំឡេងនិយាយ + ស្ងាត់)"""
    total = total or (max(e for _s, e, _f, _v in parts) + 0.5)
    work = tempfile.mkdtemp()
    files, cur = [], 0.0
    for i, (s, e, f, v) in enumerate(sorted(parts)):
        if s > cur + 1e-3:
            q = os.path.join(work, f"sil{i}.wav")
            ff("-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={s - cur:.3f}", q)
            files.append(q)
        p = os.path.join(work, f"p{i}.wav")
        ff("-f", "lavfi", "-i", f"sine=frequency={f}:duration={e - s},volume={v}",
           "-ar", "16000", "-ac", "1", p)
        files.append(p)
        cur = e
    if total > cur + 1e-3:
        q = os.path.join(work, "silend.wav")
        ff("-f", "lavfi", "-i", f"anullsrc=r=16000:cl=mono:d={total - cur:.3f}", q)
        files.append(q)
    lst = os.path.join(work, "l.txt")
    with open(lst, "w") as fh:
        fh.write("".join(f"file '{x}'\n" for x in files))
    ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", path)
    shutil.rmtree(work, ignore_errors=True)
    return path


def dur(seg):
    return float(seg["end"]) - float(seg["start"])


def main():
    tmp = tempfile.mkdtemp()

    print("\n=== 1) បន្ទាត់ 5.3 → 41.0 ជាមួយអត្ថបទត្រឹម '终结' (បញ្ហាពិតរបស់អ្នកប្រើ) ===")
    a = make_wav(os.path.join(tmp, "a.wav"),
                 [(6, 9, 200, 0.50), (38, 40, 110, 0.25)], total=42.3)
    out = SG.fit([{"start": 5.3, "end": 41.0, "zh": "终结"},
                  {"start": 41.0, "end": 42.3, "zh": "動手"}], a)
    print("   →", [(round(s["start"], 2), round(s["end"], 2), round(dur(s), 2), s["zh"]) for s in out])
    check("1a: គ្មានបន្ទាត់លើស ៨ វិនាទី", all(dur(s) <= SG.MAX_LEN + 0.01 for s in out), str([round(dur(s), 2) for s in out]))
    check("1b: ឃ្លាខ្លីត្រូវកាត់មកត្រង់សំឡេងពិត (≤ 4 វិនាទី)",
          all(dur(s) <= 4.0 for s in out), str([round(dur(s), 2) for s in out]))
    check("1c: អត្ថបទមិនបាត់", "".join(s["zh"] for s in out) == "终结動手", str([s["zh"] for s in out]))

    print("\n=== 2) បន្ទាត់វែងពិត ០ → ២៤ វិនាទី · អត្ថបទពេញ ===")
    b = make_wav(os.path.join(tmp, "b.wav"), [(0, 24, 180, 0.4)], total=24)
    txt = "你回来了我一直在等你回来吃饭吧"
    out = SG.fit([{"start": 0, "end": 24, "zh": txt}], b)
    print("   →", [(round(s["start"], 2), round(s["end"], 2), s["zh"]) for s in out])
    check("2a: គ្រប់បំណែក ≤ ៨ វិនាទី", all(dur(s) <= SG.MAX_LEN + 0.01 for s in out), str([round(dur(s), 2) for s in out]))
    check("2b: អត្ថបទមិនបាត់ (តួអក្សរដូចដើម)", "".join(s["zh"] for s in out) == txt)
    check("2c: បំបែកយ៉ាងតិច ៣ បន្ទាត់", len(out) >= 3, str(len(out)))

    print("\n=== 3) បន្ទាត់វែង + ចន្លោះស្ងាត់ + វណ្ណយុត្តិ ===")
    c = make_wav(os.path.join(tmp, "c.wav"),
                 [(0, 3.5, 150, 0.4), (4.2, 7.5, 190, 0.4), (8.2, 11.5, 150, 0.4),
                  (12.2, 16, 190, 0.4), (16.6, 19.5, 150, 0.4)], total=20)
    txt2 = "你回来了。我一直在等你，快点进来吧。饭已经做好了，来吃吧。"
    out = SG.fit([{"start": 0, "end": 20, "zh": txt2}], c)
    print("   →", [(round(s["start"], 2), round(s["end"], 2), s["zh"]) for s in out])
    check("3a: គ្រប់បំណែក ≤ ៨ វិនាទី", all(dur(s) <= SG.MAX_LEN + 0.01 for s in out), str([round(dur(s), 2) for s in out]))
    check("3b: អត្ថបទមិនបាត់", "".join(s["zh"] for s in out) == txt2)
    check("3c: កាត់ត្រង់ចន្លោះស្ងាត់ (មិនត្រួតគ្នា)",
          all(out[i]["end"] <= out[i + 1]["start"] + 0.01 for i in range(len(out) - 1)))

    print("\n=== 4) បន្ទាត់ខ្លីធម្មតា → មិនប៉ះ ===")
    segs = [{"start": 1.0, "end": 3.0, "zh": "你好"}, {"start": 3.0, "end": 4.5, "zh": "再见"}]
    out = SG.fit(segs, c)
    check("4: បន្ទាត់ខ្លីរក្សាពេលវេលាដើម",
          [(s["start"], s["end"], s["zh"]) for s in out] == [(1.0, 3.0, "你好"), (3.0, 4.5, "再见")],
          str(out))

    print("\n=== 5) គ្មានសំឡេងអានបាន → កាត់ស្មើៗ ===")
    out = SG.fit([{"start": 0, "end": 25, "zh": txt}], None)
    check("5a: គ្រប់បំណែក ≤ ៨ វិនាទី", all(dur(s) <= SG.MAX_LEN + 0.01 for s in out), str([round(dur(s), 2) for s in out]))
    check("5b: អត្ថបទមិនបាត់", "".join(s["zh"] for s in out) == txt)

    print("\n=== 6) បន្ទាត់ទទេ (hallucination) → បោះចោល ===")
    d = make_wav(os.path.join(tmp, "d.wav"), [(0, 2, 200, 0.4)], total=30)
    out = SG.fit([{"start": 0, "end": 30, "zh": ""}, {"start": 0, "end": 2, "zh": "好"}], d)
    check("6: គ្មានបន្ទាត់ទទេ", [s["zh"] for s in out] == ["好"], str(out))

    print("\n=== 7) /api/transcribe កាត់បន្ទាត់វែងស្វ័យប្រវត្តិ (route ពិត) ===")
    data = os.path.join(tmp, "data")
    os.makedirs(data, exist_ok=True)
    os.environ["KH_DATA_DIR"] = data            # ត្រូវកំណត់មុន import backend.main
    from backend import main as M               # noqa: E402
    from backend import providers as P          # noqa: E402

    vid = "longline1"
    src = os.path.join(tmp, "in.mp4")
    ff("-f", "lavfi", "-i", "color=c=black:s=160x284:r=8:d=42", "-f", "lavfi",
       "-i", "anullsrc=r=16000:cl=mono:d=42", "-shortest", "-c:v", "libx264",
       "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", src)
    shutil.copy(src, M.STORE / f"{vid}.mp4")
    real_stt = P.stt
    P.stt = lambda audio_path, cfg: [{"start": 5.3, "end": 41.0, "zh": "终结"},
                                     {"start": 41.0, "end": 42.3, "zh": "動手"}]
    try:
        res = M.transcribe(M.Vid(id=vid))
    finally:
        P.stt = real_stt
    print("   →", [(round(s["start"], 2), round(s["end"], 2), s["zh"]) for s in res])
    check("7a: route ត្រឡប់បន្ទាត់ខ្លី (≤ ៨ វិនាទី)", all(dur(s) <= SG.MAX_LEN + 0.01 for s in res),
          str([round(dur(s), 2) for s in res]))
    check("7b: អត្ថបទ STT នៅដដែល", "".join(s["zh"] for s in res) == "终结動手")
    check("7c: auto-scan តួអង្គនៅដំណើរការ", all("char" in s and "conf" in s for s in res))

    print("\n=== 8) /api/segments/fix ជួសជុលគម្រោងចាស់ (មិនត្រូវ Transcribe ម្តងទៀត) ===")
    # វីដេអូសាកល្បងមានសំឡេងពិត (ស្ងាត់ ០–៦ វិ · សំឡេង ៦–៩ វិ)
    src2 = os.path.join(tmp, "fix.mp4")
    speech = os.path.join(tmp, "sp.wav")
    ff("-f", "lavfi", "-i", "sine=frequency=210:duration=3,volume=0.5", "-ar", "16000", "-ac", "1", speech)
    ff("-f", "lavfi", "-i", "color=c=black:s=160x284:r=8:d=20",
       "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono:d=20",
       "-f", "lavfi", "-i", "color=c=red:s=160x284:r=8:d=3",
       "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", "-t", "20", src2)
    shutil.copy(src2, M.STORE / "legacy.mp4")
    fixed = M.segments_fix(M.FixLines(id="legacy", segments=[
        {"start": 5.3, "end": 41.0, "zh": "终结"}, {"start": 41.0, "end": 42.3, "zh": "動手"}]))
    print("   →", [(round(x["start"], 2), round(x["end"], 2), x["zh"]) for x in fixed["segments"]])
    check("8a: គ្មានបន្ទាត់លើស ៨ វិនាទី", all(dur(x) <= SG.MAX_LEN + 0.01 for x in fixed["segments"]))
    check("8b: អត្ថបទមិនបាត់", "".join(x["zh"] for x in fixed["segments"]) == "终结動手")
    check("8c: បានអានសំឡេងពិត (audio=True)", fixed.get("audio") is True, str(fixed.get("audio")))

    shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'=' * 52}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
        return 1
    print("ALL SEGMENTATION TESTS PASSED ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
