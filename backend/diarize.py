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
    # ឆាក (scene) — សម្រាប់ភ្ជាប់តួអង្គឆ្លងឆាក និងរាយការណ៍
    scenes = []
    try:
        from . import scenes as S
        scenes = S.detect(video, segments)
        for f, sc in zip(out, S.assign(segments, scenes)):
            f["scene"] = sc
    except Exception as e:
        print("scene analysis failed:", e, flush=True)
        for f in out:
            f["scene"] = 1
    return {"segments": out,
            "speakers": len({s.get("cluster") for s in out if s.get("cluster") is not None}),
            "scenes": [{"index": i + 1, "start": a, "end": b} for i, (a, b) in enumerate(scenes)]}


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


def _feat(x):
    """លក្ខណៈសម្រាប់បែងចែកអ្នកនិយាយ (normalized)"""
    f0 = x.get("f0") or 0.0
    z = x.get("zcr") or 0.0
    return (math.log(max(1.0, f0)), z)


def _dist(a, b):
    # F0 ជា log scale (សំឡេងតន្ត្រី) · brightness ជា linear
    return abs(a[0] - b[0]) / 0.15 + abs(a[1] - b[1]) / 0.06


def _kmeans(pts, k, iters=30):
    """k-means គ្មាន random — ចាប់ផ្តើមពី quantile នៃ F0 (រក្សាលំដាប់ដើម)"""
    n = len(pts)
    if k <= 1 or n <= k:
        return [0] * n
    order = sorted(range(n), key=lambda i: pts[i])
    cents = [list(pts[order[min(n - 1, int(round((i + 0.5) * n / k)))]]) for i in range(k)]
    labels = [0] * n
    for _ in range(iters):
        changed = False
        for i, p in enumerate(pts):
            d = [_dist(p, c) for c in cents]
            lab = d.index(min(d))
            if labels[i] != lab:
                labels[i] = lab
                changed = True
        for ci in range(k):
            mem = [pts[i] for i in range(n) if labels[i] == ci]
            if mem:
                cents[ci] = [sum(m[j] for m in mem) / len(mem) for j in range(2)]
        if not changed:
            break
    return labels


def _silhouette(pts, labels):
    ks = set(labels)
    if len(ks) < 2:
        return 0.0
    total = 0.0
    for i, p in enumerate(pts):
        own = [pts[j] for j in range(len(pts)) if labels[j] == labels[i] and j != i]
        if not own:
            continue
        a = sum(_dist(p, q) for q in own) / len(own)
        b = min((sum(_dist(p, q) for j, q in enumerate(pts) if labels[j] == k) /
                 max(1, sum(1 for j in range(len(pts)) if labels[j] == k))) for k in ks if k != labels[i])
        total += (b - a) / max(a, b) if max(a, b) else 0
    return total / len(pts)


def _cluster(items):
    """បែងចែក segment ជា speaker — k-means + silhouette (គ្មាន random)

    សំខាន់៖ clustering នេះជា **global** (គ្រប់ឆាក) ដូច្នេះតួអង្គដដែល
    ដែលនិយាយនៅឆាក ១ · ៥ · ១២ នឹងធ្លាក់ក្នុង cluster តែមួយ។
    """
    voiced = [x for x in items if (x.get("f0") or 0) > 0 and (x.get("voiced") or 0) >= 0.12]
    for x in items:
        x["cluster"] = None
    if not voiced:
        return
    pts = [_feat(x) for x in voiced]
    best_k, best_s, best_lab = 1, 0.42, [0] * len(pts)   # k=1 គឺជាតម្លៃលំនាំដើម
    # សំដីខ្លី → អនុញ្ញាត k ដល់ n (១ បន្ទាត់/អ្នក) · សំដីវែង → k ≤ n/2
    kmax = min(8, len(pts)) if len(pts) <= 6 else min(8, len(pts) // 2)
    # សំដីខ្លីៗ (តិចជាង ៦ បន្ទាត់) → អនុញ្ញាត cluster ១ បន្ទាត់ (ប្រុស ២ នាក់ និយាយតិច)
    min_size = 1 if len(pts) <= 6 else 2
    for k in range(2, kmax + 1):
        lab = _kmeans(pts, k)
        if min(lab.count(c) for c in set(lab)) < min_size:
            continue
        sc = _silhouette(pts, lab)
        if sc > best_s + 0.02:         # ត្រូវការការកើនយ៉ាងច្បាស់
            best_k, best_s, best_lab = k, sc, lab
    for x, lab in zip(voiced, best_lab):
        x["cluster"] = int(lab)

    # segment ដែលគ្មាន F0 → តាមអ្នកនិយាយជិតបំផុត (មុន/ក្រោយ)
    for idx, x in enumerate(items):
        if x.get("cluster") is None:
            prev = next((items[j] for j in range(idx - 1, -1, -1) if items[j].get("cluster") is not None), None)
            nxt = next((items[j] for j in range(idx + 1, len(items)) if items[j].get("cluster") is not None), None)
            x["cluster"] = (prev or nxt or {}).get("cluster")

    # សង្ខេបកម្រិត speaker
    for cl in {x["cluster"] for x in items if x.get("cluster") is not None}:
        mem = [x for x in items if x.get("cluster") == cl]
        f0s = sorted(x["f0"] for x in mem if x.get("f0"))
        zs = sorted(x.get("zcr") or 0 for x in mem)
        if f0s:
            for x in mem:
                x["speaker_f0"] = round(f0s[len(f0s) // 2], 1)
                x["speaker_zcr"] = round(zs[len(zs) // 2], 3)
