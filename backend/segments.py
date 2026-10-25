"""ការកាត់បន្ទាត់វែង (long-line guard) — ធានាថាគ្មានឃ្លាវែងខុសប្រក្រតី

បញ្ហាពិតដែលបានឃើញ (v1.0.23)៖
  បន្ទាត់ #1  start 5.3 → end 41.0 (៣៥,៧ វិនាទី) តែអត្ថបទត្រឹម "终结" (២ តួ)។
  s្តីដូច្នេះ៖
    · Dubbing យកសំឡេងតួអង្គ **តែមួយ** សម្រាប់ ៣៥ វិនាទី → ស្រីឮសំឡេងប្រុស
      (ឬ ប្រុសឮសំឡេងស្រី) ព្រោះភេទដែលវិភាគបាន ជាភេទរបស់អ្នកនិយាយ **ច្រើនបំផុត**
      ក្នុងចន្លោះនោះ។
    · អក្សរខ្មែរ/សំឡេង ត្រូវរត់ ៣៥ វិនាទី តែពាក្យខ្លី → មើលទៅខុសប្រក្រតី។

ដំណោះស្រាយ (ឥតគិតថ្លៃ · ffmpeg + stdlib)៖
  ១. កាត់បន្ទាត់ណាដែលវែងជាង MAX_LEN (លំនាំដើម ៨ វិនាទី)
  ២. កាត់ត្រង់ **ចន្លោះស្ងាត់** ជិតបំផុត → មិនកាត់ពាក់កណ្តាលពាក្យ
  ៣. បើអត្ថបទខ្លីខ្លាំង តែពេលវេលាវែង (hallucination លើតន្ត្រី/សំឡេងស្ងាត់)
     → រក្សាតែចន្លោះដែលមានសំឡេងនិយាយពិត ហើយបោះបង់ចន្លោះស្ងាត់ចោល
  ៤. អត្ថបទបែងចែកតាមសមាមាត្រពេលវេលា · ជ្រើសចំណុចកាត់ត្រង់សញ្ញាវណ្ណយុត្តិ

មុខងារសាធារណៈ៖
  fit(segs, audio)        → segs ថ្មី (គ្មានបន្ទាត់វែង)
  split_long(seg, audio)  → បំបែកបន្ទាត់តែមួយ
"""

import math
import re

from . import diarize as D

MAX_LEN = 8.0          # វិនាទីអតិបរមាក្នុងមួយបន្ទាត់ (ឃ្លាធម្មតា ២–៥ វិនាទី)
MIN_LEN = 0.35         # បន្ទាត់ខ្លីបំផុត
PAD = 0.12             # បន្ថែមជុំវិញសំឡេងនិយាយ
FRAME = 0.04           # 40 ms (ដូច diarize)
GAP = 0.28             # ចន្លោះស្ងាត់ ≥ 0.28 s → ចាត់ជាចំណុចកាត់បាន
SILENCE_ABS = 0.0035   # ≈ -49 dBFS — ក្រោមនេះ = ស្ងាត់
REL_SILENCE = 0.07     # ក្រោម ៧% នៃកម្រិតខ្លាំងបំផុត = ស្ងាត់
PUNCT = "，。！？、；：…,.!?;:）)」』”\"'…"

_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def _times(seg):
    """→ (start, end) ជាលេខ សុវត្ថិភាព"""
    try:
        st = float(seg.get("start") or 0.0)
    except (TypeError, ValueError):
        st = 0.0
    try:
        en = float(seg.get("end") or 0.0)
    except (TypeError, ValueError):
        en = 0.0
    st = max(0.0, st)
    if en <= st:
        en = st + MIN_LEN
    return st, en


def speech_len(text):
    """ប៉ាន់ស្មានរយៈពេលនិយាយ (វិនាទី) ពីប្រវែងអត្ថបទ

    ចិន ~ ៣,២ តួ/វិនាទី (សន្ទនាធម្មតា) · អក្សរឡាតាំង ~ ១២ តួ/វិនាទី។
    """
    t = str(text or "")
    n_cjk = len(_CJK.findall(t))
    n_other = len(re.sub(r"\s", "", _CJK.sub("", t)))
    return min(40.0, 0.31 * n_cjk + 0.075 * n_other + 0.35)


def _rms_frames(pcm, sr, frame=FRAME):
    """PCM → RMS ក្នុងមួយ frame (0..1)"""
    n = max(1, int(sr * frame))
    out = []
    for i in range(0, len(pcm) - n + 1, n):
        s = 0
        blk = pcm[i:i + n]
        for v in blk:
            s += v * v
        out.append(math.sqrt(s / len(blk)) / 32768.0)
    return out


def _islands(mask):
    """frame ដែលមានសំឡេង → [(i0, i1)) · បិទចន្លោះខ្លី (< GAP)"""
    runs, i, n = [], 0, len(mask)
    while i < n:
        if not mask[i]:
            i += 1
            continue
        j = i
        while j < n and mask[j]:
            j += 1
        runs.append([i, j])
        i = j
    gap = max(1, int(round(GAP / FRAME)))
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < gap:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    return [(a, b) for a, b in merged]


def _snap(text, pos, span=5):
    """ចំណុចកាត់ pos → ជិតសញ្ញាវណ្ណយុត្តិ/ដកឃ្លា (កុំកាត់កណ្តាលពាក្យ)"""
    n = len(text)
    if pos <= 0 or pos >= n:
        return min(max(1, pos), n - 1) if n > 1 else 1
    for d in range(span + 1):
        for p in (pos + d, pos - d):
            if 1 <= p < n and (text[p - 1] in PUNCT or text[p - 1] == " " or text[p] == " "):
                return p
    return pos


def _split_text(text, durs):
    """បែងចែកអត្ថបទតាមសមាមាត្ររយៈពេល → [chunk, …]"""
    text = str(text or "").strip()
    k = len(durs)
    if k <= 1 or not text:
        return [text] if not text else [text] + [""] * (k - 1)
    n = len(text)
    if n < k:
        return [text] + [""] * (k - 1)
    total = sum(durs) or 1.0
    cuts, acc = [], 0.0
    for i in range(k - 1):
        acc += durs[i]
        pos = int(round(n * acc / total))
        pos = _snap(text, pos)
        low = (cuts[-1] if cuts else 0) + 1
        high = n - (k - 1 - i)          # ទុកអក្សរយ៉ាងតិច ១ សម្រាប់បំណែកនៅសល់
        cuts.append(min(max(pos, low), max(low, high)))
    out, prev = [], 0
    for c in cuts + [n]:
        out.append(text[prev:c].strip())
        prev = c
    return out


def _even_split(st, en, text, max_len):
    """គ្មានសំឡេងអានបាន → កាត់ស្មើៗ តាមពេលវេលា"""
    dur = en - st
    k = max(1, int(math.ceil(dur / max_len - 1e-6)))
    if k == 1:
        return [(st, en, text)]
    step = dur / k
    spans = [(st + i * step, st + (i + 1) * step) for i in range(k)]
    parts = _split_text(text, [b - a for a, b in spans])
    out = [(a, b, t) for (a, b), t in zip(spans, parts)]
    return [(a, b, t) for a, b, t in out if t] or [(st, en, text)]


def _quiet_cut(rms, lo, hi, near=None):
    """ចំណុចស្ងាត់បំផុតក្នុង [lo, hi) → index (ជិត near បើស្មើគ្នា)"""
    lo = max(1, int(lo))
    hi = min(len(rms) - 1, int(hi))
    if hi <= lo:
        return max(1, min(int(near if near is not None else lo), len(rms) - 2) if len(rms) > 2 else 0)
    near = int(near if near is not None else (lo + hi) // 2)
    best, best_i = None, lo
    for i in range(lo, hi):
        v = rms[i - 1] + 2 * rms[i] + rms[i + 1]
        if best is None or v < best - 1e-6 or (abs(v - best) <= 1e-6 and abs(i - near) < abs(best_i - near)):
            best, best_i = v, i
    return best_i


def _energy(rms, a, b):
    return sum(rms[i] for i in range(a, min(b, len(rms))))


def _best_span(islands, rms, need_frames, max_frames):
    """ជ្រើសចន្លោះសំឡេងល្អបំផុត (សម្រាប់អត្ថបទខ្លី តែពេលវេលាវែង)"""
    if not islands:
        return None
    idx = max(range(len(islands)), key=lambda i: _energy(rms, *islands[i]))
    a, b = islands[idx]
    limit = max(max_frames, need_frames)
    for _ in range(len(islands) + 1):          # ពង្រីកទៅ island ជិតខាង (មានដែនកំណត់)
        best_j, best_ab = None, (a, b)
        for j in (idx - 1, idx + 1):
            if not (0 <= j < len(islands)):
                continue
            a2, b2 = min(a, islands[j][0]), max(b, islands[j][1])
            if (b2 - a2) <= (b - a):            # គ្មានការរីក → កុំរង្វិល
                continue
            if (b2 - a2) <= limit and (b2 - a2) <= max(need_frames * 1.6, need_frames + 4):
                if best_j is None or (b2 - a2) > (best_ab[1] - best_ab[0]):
                    best_j, best_ab = j, (a2, b2)
        if best_j is None:
            break
        a, b, idx = best_ab[0], best_ab[1], best_j
    if (b - a) > max_frames:                     # វែងពេក → កាត់យកចំណែកខ្លាំងបំផុត
        b = min(b, a + max_frames)
    return a, b


def _frames_for(sec):
    return max(1, int(round(sec / FRAME)))


def _sentences(text):
    """បំបែកជាប្រយោគ (តាមសញ្ញាចុងប្រយោគ)"""
    parts = [p.strip() for p in re.split(r"(?<=[。！？!?；;…])", str(text or ""))]
    parts = [p for p in parts if p]
    if not parts:
        return [str(text or "")]
    if len(parts) == 1 and len(parts[0]) > 24:      # គ្មានសញ្ញា → កាត់តាមកន្សោម
        parts = [p.strip() for p in re.split(r"(?<=[，,、：:])", parts[0]) if p.strip()]
    return parts or [str(text or "")]


def _pieces_from_islands(mask, cuts, pad):
    """កាត់ចន្លោះស្ងាត់ចេញ → [(i0, i1)] ដែលមានសំឡេងពិត"""
    out = []
    for i in range(len(cuts) - 1):
        i0, i1 = cuts[i], cuts[i + 1]
        voiced = [j for j in range(i0, min(i1, len(mask))) if mask[j]]
        if not voiced:
            continue
        a = max(i0, voiced[0] - pad)
        b = min(i1, voiced[-1] + 1 + pad)
        out.append((a, b))
    return out


def _one(st, en, text, audio, max_len=MAX_LEN):
    """បន្ទាត់ ១ → [(start, end, text)] (គ្មានបន្ទាត់លើស max_len)"""
    dur = en - st
    if dur <= max_len + 1e-6:
        return [(st, en, text)]
    if not audio:
        return _even_split(st, en, text, max_len)

    limit = max_len * 6 + 4
    if dur > limit + max_len:
        return _even_split(st, en, text, max_len)     # វែងខ្លាំង (កម្រ) → កាត់ស្មើ
    pcm = D.decode_pcm(audio, sr=D.SR, start=st, dur=min(dur, limit))
    rms = _rms_frames(pcm, D.SR) if pcm else []
    if not rms or max(rms) <= SILENCE_ABS:
        return _even_split(st, en, text, max_len)

    thr = max(SILENCE_ABS, REL_SILENCE * max(rms))
    mask = [v >= thr for v in rms]
    islands = _islands(mask)
    if not islands:
        return _even_split(st, en, text, max_len)

    need = speech_len(text)
    need_frames = _frames_for(need)
    max_frames = _frames_for(max_len)
    pad = max(1, _frames_for(PAD))

    a = max(0, islands[0][0] - pad)
    b = min(len(rms), islands[-1][1] + pad)
    span = (b - a) * FRAME
    if span <= max_len + 1e-9:                        # សំឡេងពិតខ្លី → កាត់សំឡេងស្ងាត់ចេញ
        return [(st + a * FRAME, min(en, st + b * FRAME), text)]

    k = max(1, int(math.ceil(span / max_len - 1e-6)))
    mn = _frames_for(MIN_LEN)
    cuts = [a]
    for i in range(1, k):
        left = k - i                                    # បំណែកដែលនៅសល់ (រួមបំណែកនេះ)
        remain = b - cuts[-1]
        target = cuts[-1] + int(round(remain / (left + 1)))
        lo = max(cuts[-1] + mn, b - left * max_frames)  # ធានាបំណែកនៅសល់គ្រប់
        hi = min(b - mn * left, cuts[-1] + max_frames)  # ធានាបំណែកនេះមិនលើស max_len
        if hi < lo:
            hi = lo = min(b - 1, cuts[-1] + max_frames)
        w = min(_frames_for(1.2), max(2, int(round((hi - lo) * 0.25)) + 2))
        cut = _quiet_cut(rms, max(lo, target - w), min(hi + 1, target + w + 1), near=target)
        cuts.append(min(max(cut, lo), hi))
    cuts.append(b)
    cuts = sorted(set(cuts))

    pieces = _pieces_from_islands(mask, cuts, pad)
    if not pieces:
        return _even_split(st, en, text, max_len)
    times = [(st + x * FRAME, min(en, st + y * FRAME)) for x, y in pieces]
    durs = [b2 - a2 for a2, b2 in times]

    # ---- អត្ថបទតិចជាងចំនួនបំណែក → ដាក់ទាំងអស់ក្នុងបំណែកដែលខ្លាំងបំផុត ----
    if len(text) <= len(pieces):
        bi = max(range(len(pieces)), key=lambda i: _energy(rms, *pieces[i]))
        (pa, pb), (ta, tb) = pieces[bi], times[bi]
        if need_frames * 1.35 < (pb - pa) * 0.55:     # អត្ថបទខ្លីខ្លាំង → រក្សាតែប្រវែងដែលអាន
            w = max(_frames_for(1.0), int(round(need_frames * 1.35)))
            best_a, best_e = pa, -1.0
            for j in range(pa, max(pa + 1, pb - w + 1)):
                e = _energy(rms, j, j + w)
                if e > best_e:
                    best_e, best_a = e, j
            pa = best_a
            pb = min(pb, pa + w)
            ta, tb = st + pa * FRAME, min(en, st + pb * FRAME)
        return [(ta, max(ta + MIN_LEN, tb), text)]

    # ---- ចន្លោះធំរវាងបំណែក (>1s) = ប្រយោគដាច់ដោយឡែក → បែងចែកតាមប្រយោគ ----
    gaps = [times[i + 1][0] - times[i][1] for i in range(len(times) - 1)]
    if any(g > 1.0 for g in gaps):
        parts = _sentences(text)
        if len(parts) > len(times):
            parts = parts[:len(times) - 1] + [" ".join(parts[len(times) - 1:])]
        return [(times[i][0], times[i][1], p) for i, p in enumerate(parts) if p]

    # ---- សំឡេងបន្តបន្ទាប់ → បែងចែកអត្ថបទតាមសមាមាត្ររយៈពេល ----
    parts = _split_text(text, durs)
    out = [(times[i][0], times[i][1], p) for i, p in enumerate(parts) if p]
    return out or [(times[0][0], times[0][1], text)]


def split_long(seg, audio=None, max_len=MAX_LEN):
    """បំបែក segment មួយ → [seg, …] (រក្សាគ្រប់ field ដើម)"""
    st, en = _times(seg)
    text = str(seg.get("zh") or "").strip()
    if not text:
        return []
    return [{**seg, "start": round(a, 3), "end": round(b, 3), "zh": t}
            for a, b, t in _one(st, en, text, audio, max_len)]


def fit(segs, audio=None, max_len=MAX_LEN):
    """បញ្ជី segment ពី STT → បញ្ជីថ្មីដែលគ្មានបន្ទាត់វែង (និងគ្មានបន្ទាត់ទទេ)"""
    out = []
    for seg in segs or []:
        if not isinstance(seg, dict):
            continue
        out.extend(split_long(seg, audio=audio, max_len=max_len))
    out.sort(key=lambda s: (float(s.get("start") or 0), float(s.get("end") or 0)))
    return out
