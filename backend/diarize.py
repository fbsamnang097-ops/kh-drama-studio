"""ការវិភាគសំឡេងពិត (speaker diarization) — គ្មាន library បន្ថែម · ប្រើតែ ffmpeg + stdlib

គោលការណ៍៖ អានសំឡេងពីវីដេអូ → វាស់ F0 (សំឡេងខ្ពស់/ទាប) និងលក្ខណៈសំឡេង
ក្នុងចន្លោះពេលនីមួយៗ → បែងចែកជា "អ្នកនិយាយ" (speaker cluster) ដោយខ្លួនឯង។

ហេតុអ្វីត្រូវការ៖ ឈ្មោះចិន ឬអត្ថបទ មិនអាចប្រាប់ភេទ/អាយុបានត្រឹមត្រូវទេ។
សំឡេងពិត (F0) ជាភស្តុតាងខ្លាំងបំផុត៖
  · ប្រុសពេញវ័យ ~ 85–155 Hz
  · ស្រីពេញវ័យ ~ 165–255 Hz
  · ក្មេង           ~ 250–400 Hz
  · ចាស់            F0 ទាប + ញ័រខ្លាំង (jitter) + និយាយយឺត

គ្មាន numpy → គណនាដោយ pure Python (គ្រប់គ្រាន់សម្រាប់ ១៥–២០ frame ក្នុងមួយបន្ទាត់)។
"""

import array
import math
import os
import subprocess
import tempfile
from collections import Counter

SR = 8000            # 8 kHz គ្រប់គ្រាន់សម្រាប់ F0 (50–500 Hz)
FRAME = 0.040        # 40 ms
F0_MIN, F0_MAX = 65.0, 420.0
VOICED_CLARITY = 0.30     # autocorrelation peak → ចាត់ថាជាសំឡេងនិយាយ


def _ffmpeg_bin():
    """ffmpeg ក្នុង PATH ឬភ្ជាប់មកជាមួយ (PyInstaller / imageio)"""
    import shutil
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:                                   # exe build: ffmpeg នៅក្បែរ executable
        import sys
        cand = os.path.join(os.path.dirname(sys.executable), "ffmpeg")
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    return "ffmpeg"


def decode_pcm(video, sr=SR, start=None, dur=None):
    """វីដេអូ → s16le mono PCM (array of int) សម្រាប់វិភាគ"""
    cmd = [_ffmpeg_bin(), "-hide_banner", "-nostats", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", f"{max(0.0, start):.3f}"]
    if dur is not None:
        cmd += ["-t", f"{max(0.05, dur):.3f}"]
    cmd += ["-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode or not r.stdout:
        return array.array("h")
    a = array.array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    return a


def _rms(frame):
    if not frame:
        return 0.0
    s = 0
    for v in frame:
        s += v * v
    return math.sqrt(s / len(frame)) / 32768.0


def _f0(frame, sr=SR):
    """Autocorrelation F0 → (Hz, clarity 0..1)"""
    n = len(frame)
    if n < 64:
        return 0.0, 0.0
    # ដក mean (DC) និងវាស់ energy
    mean = sum(frame) / n
    x = [v - mean for v in frame]
    e0 = sum(v * v for v in x)
    if e0 <= 1e-6:
        return 0.0, 0.0
    lo, hi = int(sr / F0_MAX), int(sr / F0_MIN)          # lag range
    hi = min(hi, n - 2)
    if hi <= lo:
        return 0.0, 0.0
    best, best_lag = 0.0, 0
    # ជំហាន ២ ដើម្បីលឿន រួចសម្អាតជុំវិញ
    for lag in range(lo, hi + 1, 2):
        s = 0
        for i in range(0, n - lag):
            s += x[i] * x[i + lag]
        r = s / e0
        if r > best:
            best, best_lag = r, lag
    for lag in (best_lag - 1, best_lag + 1):
        if lo <= lag <= hi:
            s = 0
            for i in range(0, n - lag):
                s += x[i] * x[i + lag]
            r = s / e0
            if r > best:
                best, best_lag = r, lag
    if best_lag <= 0:
        return 0.0, 0.0
    return sr / best_lag, max(0.0, min(1.0, best))


def _zcr(frame):
    if len(frame) < 2:
        return 0.0
    c = 0
    for i in range(1, len(frame)):
        if (frame[i - 1] < 0) != (frame[i] < 0):
            c += 1
    return c / (len(frame) - 1)


def features(pcm, sr=SR, max_frames=24):
    """សំឡេង ១ ចន្លោះ → លក្ខណៈសំឡេង (F0 · clarity · energy · zcr)"""
    n = len(pcm)
    if n < int(sr * 0.15):
        return {"voiced": 0.0, "f0": 0.0, "clarity": 0.0, "rms": 0.0, "zcr": 0.0, "frames": 0}
    win = int(sr * FRAME)
    step = max(win, n // max(1, max_frames))
    f0s, cls, rmss, zcrs = [], [], [], []
    for s in range(0, n - win, step):
        fr = pcm[s:s + win]
        r = _rms(fr)
        if r < 0.004:                    # ស្ងាត់ / សំឡេងផ្ទៃខាងក្រោយ
            continue
        f, c = _f0(fr, sr)
        if c >= VOICED_CLARITY and F0_MIN <= f <= F0_MAX:
            f0s.append(f)
            cls.append(c)
        rmss.append(r)
        zcrs.append(_zcr(fr))
    frames = max(1, (n // step))
    voiced = len(f0s) / frames
    if not f0s:
        return {"voiced": round(voiced, 3), "f0": 0.0, "clarity": 0.0,
                "rms": round(sum(rmss) / len(rmss), 4) if rmss else 0.0,
                "zcr": round(sum(zcrs) / len(zcrs), 3) if zcrs else 0.0,
                "frames": len(rmss), "jitter": 0.0, "rate": 0.0}
    f0s.sort()
    med = f0s[len(f0s) // 2]
    # jitter = ការប្រែប្រួល F0 (ចាស់/ញ័រ → ខ្ពស់)
    jit = (sum(abs(a - med) for a in f0s) / len(f0s)) / med if med else 0.0
    return {
        "voiced": round(voiced, 3),
        "f0": round(med, 1),
        "clarity": round(sum(cls) / len(cls), 3),
        "rms": round(sum(rmss) / len(rmss), 4) if rmss else 0.0,
        "zcr": round(sum(zcrs) / len(zcrs), 3) if zcrs else 0.0,
        "jitter": round(jit, 3),
        "frames": len(rmss),
    }


def analyze_segments(video, segments, sr=SR, progress=None):
    """វិភាគគ្រប់ segment ក្នុងវីដេអូ → លក្ខណៈសំឡេង + speaker cluster

    ប្រើ temp wav តែមួយសម្រាប់វីដេអូទាំងមូល (លឿនជាងកាត់ทีละ segment)
    """
    total = 0.0
    for s in segments:
        try:
            total = max(total, float(s.get("end") or 0))
        except (TypeError, ValueError):
            pass
    if total <= 0:
        return {"segments": [], "speakers": 0, "error": "គ្មានពេលវេលា segment"}

    out = []
    step = 0.0
    for i, seg in enumerate(segments):
        try:
            st, en = float(seg.get("start") or 0), float(seg.get("end") or 0)
        except (TypeError, ValueError):
            st, en = 0.0, 0.0
        dur = max(0.05, en - st)
        pcm = decode_pcm(video, sr=sr, start=st, dur=dur)
        f = features(pcm, sr=sr)
        f["index"] = i
        f["start"], f["end"] = round(st, 2), round(en, 2)
        out.append(f)
        step += 1
        if progress:
            progress(step / max(1, len(segments)))
    _cluster(out)
    return {"segments": out, "speakers": len({s.get("cluster") for s in out if s.get("cluster") is not None})}


# ---------- បែងចែកអ្នកនិយាយ (clustering) ----------
GENDER_FEMALE_F0 = 165.0
CHILD_F0 = 250.0


def voice_class(f):
    """F0 → (gender, age, confidence) — ភស្តុតាងពីសំឡេងពិត"""
    f0 = f.get("f0") or 0.0
    voiced = f.get("voiced") or 0.0
    clarity = f.get("clarity") or 0.0
    if f0 <= 0 or voiced < 0.12 or clarity < 0.25:
        return ("unknown", "unknown", 0.0)
    # ភាពជឿជាក់ពី ចំនួន frame ដែលមានសំឡេង + clarity
    conf = min(0.95, 0.45 + 0.35 * min(1.0, voiced) + 0.25 * clarity)
    if f0 >= CHILD_F0:
        return ("female", "child", conf) if f0 < 330 else ("unknown", "child", conf)
    if f0 >= GENDER_FEMALE_F0:
        return ("female", "adult", conf)
    if f0 >= 70:
        return ("male", "adult", conf)
    return ("unknown", "unknown", 0.0)


def _cluster(items, rel=0.13):
    """បែងចែក segment ជា speaker តាម F0 + clarity (គ្មាន random)"""
    voiced = [x for x in items if (x.get("f0") or 0) > 0 and (x.get("voiced") or 0) >= 0.12]
    for x in items:
        x["cluster"] = None
    if not voiced:
        return
    # seed: តម្រៀបតាម F0 រួចបំបែកនៅចន្លោះ > rel
    voiced.sort(key=lambda x: x["f0"])
    groups = [[voiced[0]]]
    for x in voiced[1:]:
        if x["f0"] > groups[-1][-1]["f0"] * (1 + rel):
            groups.append([x])
        else:
            groups[-1].append(x)
    # merge groups ដែល F0 ជិតគ្នា (បើមាន seed តូច)
    for gi, g in enumerate(groups):
        mean = sum(x["f0"] for x in g) / len(g)
        for x in g:
            x["cluster"] = gi
        g_mean = mean
        groups[gi] = g
    # ចាត់ segment ដែលគ្មាន F0 ទៅ cluster ជិតបំផុត (បើមានបន្ទាត់ជុំវិញ)
    means = {i: sum(x["f0"] for x in g) / len(g) for i, g in enumerate(groups)}
    for idx, x in enumerate(items):
        if x.get("cluster") is None:
            prev = next((items[j] for j in range(idx - 1, -1, -1) if items[j].get("cluster") is not None), None)
            nxt = next((items[j] for j in range(idx + 1, len(items)) if items[j].get("cluster") is not None), None)
            x["cluster"] = (prev or nxt or {}).get("cluster")
    # speaker-level summary
    for gi in means:
        mem = [x for x in items if x.get("cluster") == gi]
        f0s = [x["f0"] for x in mem if x.get("f0")]
        if f0s:
            f0s.sort()
            for x in mem:
                x["speaker_f0"] = round(f0s[len(f0s) // 2], 1)
