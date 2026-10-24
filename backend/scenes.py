"""Scene detection — បែងចែកវីដេអូជា "ឆាក" (scene) សម្រាប់ការវិភាគតួអង្គ

ប្រើពីរ៉ែពីរ៖
  1. ffmpeg scene-change detection (ភ្លឺ/ងងឹត ឬកាត់ឆាក)
  2. បើរកមិនឃើញ → បំបែកតាមចន្លោះសម្ងាត់របស់សម្ដី (> 2.5 វិនាទី)
  3. បើគ្មានអ្វីទាល់តែសោះ → ឆាកតែមួយ

ហេតុអ្វីសំខាន់៖ "តួអង្គ A និយាយក្នុងឆាក ១ · ៥ · ១២ ត្រូវប្រើសំឡេងដដែល" —
ត្រូវដឹងថាឆាកណាមួយ ដើម្បីភ្ជាប់តួអង្គឆ្លងឆាក និងរាយការណ៍បានត្រឹមត្រូវ។
"""

import re
import shutil
import subprocess


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import sys, os
        cand = os.path.join(os.path.dirname(sys.executable), "ffmpeg")
        if os.path.exists(cand):
            return cand
    except Exception:
        pass
    return "ffmpeg"


def detect(video, segments=None, threshold=0.35, max_scenes=400):
    """→ [(start, end)] តាមលំដាប់ពេលវេលា"""
    duration = 0.0
    for s in segments or []:
        try:
            duration = max(duration, float(s.get("end") or 0))
        except (TypeError, ValueError):
            pass
    cuts = []
    try:
        r = subprocess.run(
            [_ffmpeg(), "-hide_banner", "-nostats", "-i", str(video),
             "-filter:v", f"select='gt(scene,{threshold})',metadata=print",
             "-an", "-f", "null", "-"],
            capture_output=True, text=True, timeout=180)
        for m in re.finditer(r"pts_time:([0-9.]+)", r.stderr):
            t = float(m.group(1))
            if t > 0.4:
                cuts.append(t)
    except Exception as e:
        print("scene detect failed:", e, flush=True)
        cuts = []

    # fallback ១៖ ចន្លោះសម្ងាត់រវាងសម្ដី
    if len(cuts) < 1 and segments:
        prev_end = None
        for s in segments:
            try:
                st, en = float(s.get("start") or 0), float(s.get("end") or 0)
            except (TypeError, ValueError):
                continue
            if prev_end is not None and st - prev_end > 2.5:
                cuts.append(round((prev_end + st) / 2, 2))
            prev_end = en

    cuts = sorted(set(round(c, 2) for c in cuts))[:max_scenes]
    end = duration or (cuts[-1] if cuts else 0.0)
    if not cuts:
        return [(0.0, round(end, 2))] if end else []
    bounds = [0.0] + [c for c in cuts if 0.0 < c < (end or 1e9)] + [round(end, 2)]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a > 0.05:
            out.append((round(a, 2), round(b, 2)))
    return out or [(0.0, round(end, 2))]


def assign(segments, scenes):
    """បន្ថែម scene index ទៅ segment នីមួយៗ (ចាប់ពី ១)"""
    out = []
    for s in segments or []:
        st = 0.0
        try:
            st = float(s.get("start") or 0)
        except (TypeError, ValueError):
            pass
        idx = 0
        for i, (a, b) in enumerate(scenes or []):
            if a <= st < b:
                idx = i
                break
        else:
            if scenes:
                idx = len(scenes) - 1
        out.append(idx + 1 if scenes else 1)
    return out
