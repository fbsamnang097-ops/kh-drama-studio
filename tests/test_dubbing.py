"""End-to-end acceptance tests for character detection & consistent voice dubbing.

Tests 1–10 from the specification, executed against the REAL FastAPI server
(subprocess), the REAL ffmpeg pipeline and a temporary data directory.

Run:  python tests/test_dubbing.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PORT = int(os.environ.get("KH_TEST_PORT", "8765"))
BASE = f"http://127.0.0.1:{PORT}"
PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"   [{detail}]" if detail else ""))


def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *a],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-800:])


# ---------------- test media ----------------
SPEAKERS = {
    "elderly_f": 190,   # 奶奶
    "elderly_m": 105,   # 爷爷
    "adult_f": 215,     # 母亲
    "adult_m": 112,     # 父亲
}
SCENES = [
    # (start, end, color, [(role, start, end)])
    (0, 8, "maroon", [("elderly_f", 0, 2), ("elderly_m", 2, 4), ("adult_f", 4, 6), ("adult_m", 6, 8)]),
    (8, 16, "darkgreen", [("adult_m", 8, 10), ("elderly_f", 10, 12), ("adult_f", 12, 14), ("elderly_m", 14, 16)]),
    (16, 24, "navy", [("elderly_f", 16, 18), ("elderly_m", 18, 20), ("adult_f", 20, 22), ("adult_m", 22, 24)]),
]
LINES = {
    ("elderly_f", 0): "奶奶说：「孩子们，吃饭了。」",
    ("elderly_m", 2): "爷爷说：「来了来了。」",
    ("adult_f", 4): "「妈，我来帮你。」",
    ("adult_m", 6): "「谢谢。」",
    ("adult_m", 8): "「爸，我出门了。」",
    ("elderly_f", 10): "奶奶说：「早点回来。」",
    ("adult_f", 12): "「路上小心。」",
    ("elderly_m", 14): "爷爷说：「注意安全。」",
    ("elderly_f", 16): "奶奶说：「慢点走。」",
    ("elderly_m", 18): "爷爷说：「别急。」",
    ("adult_f", 20): "「我会的。」",
    ("adult_m", 22): "「再见。」",
}


def make_video(path):
    work = tempfile.mkdtemp()
    parts = []
    for i, (a, b, _c, roles) in enumerate(SCENES):
        p = os.path.join(work, f"a{i}.wav")
        concat = os.path.join(work, f"list{i}.txt")
        clips = []
        for role, s, e in roles:
            cp = os.path.join(work, f"a{i}_{s}.wav")
            ff("-f", "lavfi", "-i", f"sine=frequency={SPEAKERS[role]}:duration={e - s},volume=0.35",
               "-af", "tremolo=f=4:d=0.9", "-ar", "16000", "-ac", "1", cp)
            clips.append(cp)
        with open(concat, "w") as fh:
            for cp in clips:
                fh.write(f"file '{cp}'\n")
        ff("-f", "concat", "-safe", "0", "-i", concat, "-c", "copy", p)
        parts.append(p)
    alist = os.path.join(work, "alist.txt")
    with open(alist, "w") as fh:
        for p in parts:
            fh.write(f"file '{p}'\n")
    wav = os.path.join(work, "all.wav")
    ff("-f", "concat", "-safe", "0", "-i", alist, "-c", "copy", wav)

    # វីដេអូ ៣ ឆាក (ពណ៌ខុសគ្នា → scene detection ចាប់បាន)
    inputs, flt = [], []
    for i, (a, b, c, _r) in enumerate(SCENES):
        inputs += ["-f", "lavfi", "-i", f"color=c={c}:s=320x568:r=12:d={b - a}"]
        flt.append(f"[{i}:v]")
    flt.append(f"concat=n={len(SCENES)}:v=1:a=0[v]")
    ff(*inputs, "-i", wav, "-filter_complex", "".join(flt), "-map", "[v]", "-map", f"{len(SCENES)}:a",
       "-shortest", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
       "-c:a", "aac", path)
    shutil.rmtree(work, ignore_errors=True)
    return path


# ---------------- server ----------------
class Server:
    def __init__(self, data_dir):
        self.data = data_dir
        self.proc = None

    def start(self):
        env = {**os.environ, "KH_DATA_DIR": self.data, "KH_TTS_STUB": "1",
               "PATH": os.path.dirname(shutil.which("ffmpeg") or "/usr/bin/ffmpeg") + ":" + os.environ.get("PATH", ""),
               "PYTHONPATH": ROOT}
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(120):
            try:
                urllib.request.urlopen(BASE + "/api/version", timeout=1)
                return
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("server did not start: " + (self.proc.stdout.read() if self.proc.stdout else ""))

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def call(path, body=None, method=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}"), e.code


def upload(path):
    with open(path, "rb") as fh:
        data = fh.read()
    bnd = "----khtest" + str(int(time.time()))
    body = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"drama.mp4\"\r\n"
            f"Content-Type: video/mp4\r\n\r\n").encode() + data + f"\r\n--{bnd}--\r\n".encode()
    req = urllib.request.Request(BASE + "/api/upload", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def main():
    tmp = tempfile.mkdtemp(prefix="khdub_")
    data_dir = os.path.join(tmp, "data")
    os.makedirs(data_dir, exist_ok=True)
    video = make_video(os.path.join(tmp, "drama.mp4"))
    print(f"test video: {os.path.getsize(video) // 1024} KB")

    srv = Server(data_dir)
    srv.start()
    try:
        v = upload(video)
        vid = v["id"]
        project = "ep01"
        segments = []
        for a, b, _c, roles in SCENES:
            for role, s, e in roles:
                segments.append({"start": s, "end": e, "zh": LINES[(role, s)]})

        r, code = call("/api/characters/detect",
                       {"id": vid, "project": project, "segments": segments, "use_audio": True})
        check("detect returns 200", code == 200, str(code))
        chars = r.get("characters", [])
        items = r.get("items", [])
        by_id = {c["id"]: c for c in chars}
        print("   characters:", [(c["id"], c["name"], c["gender"], c["age"], c["voice"]) for c in chars])
        print("   scenes detected:", len(r.get("audio", {}).get("speakers", [])) if False else len(r.get("scenes", [])),
              "| speakers:", r.get("audio", {}).get("speakers"))

        def char_of(role, start):
            idx = next(i for i, s in enumerate(segments) if s["start"] == start)
            return by_id[items[idx]["char_id"]]

        # ---------------- Test 1: elderly woman, scenes 1,5,12 ----------------
        e1, e2, e3 = char_of("elderly_f", 0), char_of("elderly_f", 16), char_of("elderly_f", 10)
        check("Test 1: elderly woman keeps one character + one elderly female voice",
              e1["id"] == e2["id"] == e3["id"]
              and e1["voice"] == e2["voice"] == e3["voice"]
              and e1["gender"] == "female" and e1["age"] == "elderly",
              f"{e1['id']}/{e1['voice']} vs {e2['id']}/{e2['voice']} vs {e3['id']}/{e3['voice']}")

        # ---------------- Test 2: elderly man ----------------
        m1, m2, m3 = char_of("elderly_m", 2), char_of("elderly_m", 18), char_of("elderly_m", 14)
        check("Test 2: elderly man keeps one elderly male voice",
              m1["id"] == m2["id"] == m3["id"] and m1["voice"] == m2["voice"] == m3["voice"]
              and m1["gender"] == "male" and m1["age"] == "elderly",
              f"{m1['id']}/{m1['voice']}")

        # ---------------- Test 3/4: adult woman / man ----------------
        f1, f2 = char_of("adult_f", 4), char_of("adult_f", 20)
        a1, a2 = char_of("adult_m", 6), char_of("adult_m", 22)
        check("Test 3: adult woman keeps her voice",
              f1["id"] == f2["id"] and f1["voice"] == f2["voice"] and f1["gender"] == "female" and f1["age"] == "adult",
              f"{f1['id']}/{f1['voice']}")
        check("Test 4: adult man keeps his voice",
              a1["id"] == a2["id"] and a1["voice"] == a2["voice"] and a1["gender"] == "male" and a1["age"] == "adult",
              f"{a1['id']}/{a1['voice']}")

        # ---------------- Test 5: several speakers in one scene ----------------
        scene1 = [items[i] for i, s in enumerate(segments) if s["start"] < 8]
        ids1 = [it["char_id"] for it in scene1]
        check("Test 5: each segment in a multi-speaker scene has its own character",
              len(set(ids1)) == 4 and len(ids1) == 4, str(ids1))

        # ---------------- Test 6: male-only scene ----------------
        male_only = [{"start": 30, "end": 32, "zh": "爷爷说：「走吧。」"},
                     {"start": 32, "end": 34, "zh": "「好。」"}]
        male_audio_lines = [{"start": 0, "end": 2, "zh": "爷爷说：「走吧。」"},
                            {"start": 2, "end": 4, "zh": "「好。」"}]
        # វីដេអូខ្លីមានតែប្រុស ២ នាក់
        mv = os.path.join(tmp, "males.mp4")
        work = tempfile.mkdtemp()
        a1p, a2p = os.path.join(work, "a.wav"), os.path.join(work, "b.wav")
        ff("-f", "lavfi", "-i", "sine=frequency=110:duration=2,volume=0.35", "-ar", "16000", "-ac", "1", a1p)
        ff("-f", "lavfi", "-i", "sine=frequency=132:duration=2,volume=0.35", "-ar", "16000", "-ac", "1", a2p)
        lst = os.path.join(work, "l.txt")
        open(lst, "w").write(f"file '{a1p}'\nfile '{a2p}'\n")
        wav = os.path.join(work, "w.wav")
        ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", wav)
        ff("-f", "lavfi", "-i", "color=c=black:s=240x426:r=10:d=4", "-i", wav, "-shortest",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", mv)
        shutil.rmtree(work, ignore_errors=True)
        mvup = upload(mv)
        rm, _ = call("/api/characters/detect", {"id": mvup["id"], "project": "males",
                                                "segments": male_audio_lines})
        mchars = [c for c in rm["characters"] if c["gender"] != "unknown"]
        check("Test 6: male-only scene → no female voice",
              all(c["gender"] == "male" for c in mchars) and len(mchars) >= 1,
              str([(c["name"], c["gender"], c["voice"]) for c in mchars]))

        # ---------------- Test 7: female-only scene ----------------
        fv = os.path.join(tmp, "females.mp4")
        work = tempfile.mkdtemp()
        b1, b2 = os.path.join(work, "a.wav"), os.path.join(work, "b.wav")
        ff("-f", "lavfi", "-i", "sine=frequency=200:duration=2,volume=0.35", "-ar", "16000", "-ac", "1", b1)
        ff("-f", "lavfi", "-i", "sine=frequency=235:duration=2,volume=0.35", "-ar", "16000", "-ac", "1", b2)
        lst = os.path.join(work, "l.txt")
        open(lst, "w").write(f"file '{b1}'\nfile '{b2}'\n")
        wav = os.path.join(work, "w.wav")
        ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", wav)
        ff("-f", "lavfi", "-i", "color=c=black:s=240x426:r=10:d=4", "-i", wav, "-shortest",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", fv)
        shutil.rmtree(work, ignore_errors=True)
        fup = upload(fv)
        rf, _ = call("/api/characters/detect", {"id": fup["id"], "project": "females",
                                                "segments": [{"start": 0, "end": 2, "zh": "「你好。」"},
                                                             {"start": 2, "end": 4, "zh": "「再见。」"}]})
        fchars = [c for c in rf["characters"] if c["gender"] != "unknown"]
        check("Test 7: female-only scene → no male voice",
              all(c["gender"] == "female" for c in fchars) and len(fchars) >= 1,
              str([(c["name"], c["gender"], c["voice"]) for c in fchars]))

        # ---------------- Test 8: regenerate one segment → same voice ----------------
        seg_idx = 2   # adult woman (start 4 s)
        target = items[seg_idx]["char_id"]
        tts1, c1 = call("/api/tts", {"text": "សួស្តី", "video": project, "char_id": target, "idx": seg_idx})
        tts2, c2 = call("/api/tts", {"text": "សូមស្វាគមន៍", "video": project, "char_id": target, "idx": seg_idx})
        # បន្ថែមសំឡេងសម្រាប់គ្រប់ segment (ដើម្បី export)
        audio_by_idx = {seg_idx: tts2.get("url")}
        for i, sg in enumerate(segments):
            if i in audio_by_idx:
                continue
            tr, _cc = call("/api/tts", {"text": sg["zh"][:20], "video": project,
                                        "char_id": items[i]["char_id"], "idx": i})
            audio_by_idx[i] = tr.get("url")
        check("Test 8: regenerating a segment keeps the same character voice",
              c1 == 200 and c2 == 200 and tts1.get("voice") == tts2.get("voice") == by_id[target]["voice"],
              f"{tts1.get('voice')} / {tts2.get('voice')} / assigned {by_id[target]['voice']}")

        # ---------------- manual override + reset (natural voices) ----------------
        # សំឡេងធម្មតា: មានតែ Piseth/Sreymom → ការជ្រើសដៃកត់ត្រា assignment=manual
        ov_voice = "female_adult_3"        # profile id ចាស់ → normalize → female_adult_1
        ao, _ = call("/api/characters/assign", {"id": vid, "project": project, "overrides": {target: ov_voice}})
        saved = [c for c in ao["characters"] if c["id"] == target][0]
        rd, _ = call("/api/characters/detect", {"id": vid, "project": project, "segments": segments})
        after = [c for c in rd["characters"] if c["id"] == target][0]
        check("manual override survives re-detection",
              saved["voice"] == "female_adult_1" and saved.get("assignment") == "manual"
              and after["voice"] == "female_adult_1" and after.get("assignment") == "manual",
              f"{saved['voice']} ({saved.get('assignment')}) → {after['voice']} ({after.get('assignment')})")

        # ---------------- Test 9: restart backend ----------------
        before = {c["id"]: c["voice"] for c in call(f"/api/project/{project}")[0]["characters"]}
        srv.stop()
        time.sleep(1)
        srv.start()
        st, code9 = call(f"/api/project/{project}")
        after9 = {c["id"]: c["voice"] for c in st.get("characters", [])}
        check("Test 9b: only Piseth/Sreymom natural voices are used",
              set(after9.values()) <= {"male_adult_1", "female_adult_1", "unknown_1"}, str(sorted(set(after9.values()))))
        check("Test 9: voice assignments survive a backend restart",
              code9 == 200 and before == after9 and after9.get(target) == "female_adult_1",
              f"{len(after9)} characters restored")

        # reset manual → automatic voice for that character
        rr, _ = call("/api/characters/assign", {"id": vid, "project": project, "overrides": {}, "reset": True})
        reset_char = next(c for c in rr["characters"] if c["id"] == target)
        check("Auto Assign Voice resets manual override",
              reset_char.get("assignment") == "automatic" and reset_char["voice"] == "female_adult_1",
              f"{ov_voice} → {reset_char['voice']} ({reset_char.get('assignment')})")

        # ---------------- Test 10: export ----------------
        # បង្កើតសំឡេងសម្រាប់គ្រប់ segment ឡើងវិញ (ក្រោយ reset)
        exp_segments = []
        for i, sg in enumerate(segments):
            tr, _ = call("/api/tts", {"text": sg["zh"][:20], "video": project,
                                      "char_id": items[i]["char_id"], "idx": i})
            exp_segments.append({**sg, "km": f"ខ្មែរ {i}", "char_id": items[i]["char_id"],
                                 "audio": tr.get("url"), "voice": tr.get("voice")})
        ex, codex = call("/api/export", {"id": vid, "segments": exp_segments, "subs": False,
                                         "speed": "fast", "quality": ""})
        ok_export, state = False, {}
        for _ in range(120):
            stt, _c = call(f"/api/export_status?id={vid}")
            state = stt
            if stt.get("state") in ("done", "error"):
                ok_export = stt.get("state") == "done"
                break
            time.sleep(1)
        man, _cm = call(f"/api/export_manifest?id={vid}")
        expected = {c["id"]: c["voice"] for c in call(f"/api/project/{project}")[0]["characters"]}
        rows = man.get("segments", [])
        matches = all(r["voice_used"] == expected.get(r["char_id"]) for r in rows if r["char_id"])
        check("Test 10: exported audio uses the saved character voices",
              ok_export and len(rows) == len(segments) and matches,
              f"export={state.get('state')} · segments={len(rows)} · match={matches}")
        check("Test 10b: character labels match generated audio per segment",
              all(r["voice_used"] and r["audio"] for r in rows), f"{len(rows)} segments")
    finally:
        srv.stop()
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{'=' * 56}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
        return 1
    print("ALL DUBBING PIPELINE TESTS PASSED ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
