"""Character identity — បញ្ចូលភស្តុតាងសំឡេង (diarization) + អត្ថបទ + ការស្គាល់ឈ្មោះ

លំដាប់អាទិភាព (តាមតម្រូវការ)៖
  1. សំឡេងពិត (F0 / diarization)  → ភេទ និងអាយុ
  2. សម្រង់សម្ដី និងកិរិយាសព្ទនិយាយ (អ្នកណានិយាយ)
  3. ឈ្មោះ + ពាក្យសម្ព័ន្ធ (爷爷/小姐/孩子)
  4. ការឆ្លាស់វេនសន្ទនា
  5. បើមិនដឹង → "unknown" (មិនប្រឌិតភេទ)

លទ្ធផល៖ តួអង្គ (character) ថេរពេញរឿង — cluster មួយ = តួអង្គមួយ = សំឡេងមួយ។
"""

import hashlib
import json

from . import cast as C
from . import diarize as D
from . import voices as V
from . import registry as R

# ---------- ពាក្យបញ្ជាក់អាយុ/ស្ទីល ----------
TEEN_WORDS = ("少年", "少女", "学生", "同学", "高中生", "大学生", "年轻人", "小伙")
STYLE_WORDS = {
    "angry": ("怒", "吼", "骂", "滚", "闭嘴", "混蛋", "该死", "气"),
    "sad": ("哭", "泪", "难过", "伤心", "呜"),
    "happy": ("笑", "哈哈", "开心", "高兴"),
    "whisper": ("小声", "低声", "轻声", "悄悄", "喃喃"),
    "shout": ("大声", "喊", "叫", "吼"),
}
COLOR_POOL = ["#38bdf8", "#f472b6", "#f59e0b", "#34d399", "#a78bfa", "#fb7185",
              "#22d3ee", "#facc15", "#4ade80", "#f97316"]


def _style(text):
    for k, words in STYLE_WORDS.items():
        if any(w in str(text or "") for w in words):
            return k
    return "normal"


def _vname(i):
    """c1 → តួអង្គ A (ងាយអានជាងលេខ)"""
    n = i
    s = ""
    while True:
        s = chr(ord("A") + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


def _cluster_evidence(rows):
    """ភស្តុតាងសំឡេងក្នុង cluster មួយ → ភេទ/អាយុ/ភាពជឿជាក់"""
    gw, aw = {}, {}
    for r in rows:
        a = r.get("audio") or {}
        g, age, conf = D.voice_class(a) if a else ("unknown", "unknown", 0.0)
        if conf > 0:
            gw[g] = gw.get(g, 0) + conf
            aw[age] = aw.get(age, 0) + conf
    gender = max(gw.items(), key=lambda x: x[1])[0] if gw else "unknown"
    age = max(aw.items(), key=lambda x: x[1])[0] if aw else "unknown"
    total = sum(gw.values())
    conf = min(0.95, total / max(1, len(rows))) if total else 0.0
    return gender, age, round(conf, 2)


def resolve(lines, audio=None, video_id="", voicebook=None, previous=None,
            con=None, pid=None, provider="edge", reassign=False):
    """lines: [{zh,start,end}] · audio: diarize.analyze_segments(...)

    → {characters, items, summary, limitations, video_id}
    """
    lines = list(lines or [])
    texts = [str(l.get("zh") or "") for l in lines]
    text_cast = C.build_cast(texts)
    names_all = C.find_names(texts)
    audio_segs = (audio or {}).get("segments") or []

    # ---- ជំហាន ១៖ ភស្តុតាងតាមបន្ទាត់ ----
    rows = []
    for i, line in enumerate(lines):
        raw = texts[i]
        role, tconf = C.detect(raw, text_cast)
        q = C.QUOTED.search(raw)
        outside = raw[:q.start()] if q else raw
        tail = raw[q.end():] if q else ""
        # ឈ្មោះអ្នកនិយាយ = ក្រៅសម្រង់សម្ដី (មុន ឬ ក្រោយ) មិនមែនក្នុងសម្ដី
        narr_part = (outside + " " + tail).strip()
        name = C._name_in(narr_part, text_cast)[1] or C.name_in_line(narr_part, names_all)
        a = audio_segs[i] if i < len(audio_segs) else {}
        rows.append({
            "index": i, "zh": raw, "role_text": role, "conf_text": tconf,
            "name": name, "audio": a, "cluster": a.get("cluster"),
            "style": _style(raw),
        })

    # ---- ជំហាន ២៖ បង្កើតតួអង្គពី cluster ----
    characters, by_cluster, order = [], {}, []
    narration_rows = [r for r in rows if r["role_text"] == C.NARR]
    dialogue_rows = [r for r in rows if r["role_text"] != C.NARR]

    # អ្នកនិទាន (បើមានបន្ទាត់ពិពណ៌នា)
    narrator_id = None
    if narration_rows:
        g = "male"
        a0 = next((r["audio"] for r in narration_rows if r["audio"]), {})
        if a0:
            ag, _aa, ac = D.voice_class(a0)
            if ac >= 0.5:
                g = ag if ag in ("male", "female") else "male"
        narrator_id = "narrator"
        characters.append({
            "id": narrator_id, "name": "អ្នកនិទាន", "gender": g, "age": "adult",
            "role": C.NARR, "kind": "narrator", "cluster": None,
            "conf": 0.9, "lines": len(narration_rows),
            "voice": "narrator_male" if g == "male" else "narrator_female",
            "evidence": "text", "color": "#fbbf24",
        })

    # cluster → តួអង្គ
    clusters = []
    for r in dialogue_rows:
        if r["cluster"] is not None and r["cluster"] not in clusters:
            clusters.append(r["cluster"])
    clusters.sort()

    used_voices = []
    taken = set()          # ឈ្មោះដែលបានផ្តល់ទៅតួអង្គរួច
    for ci, cl in enumerate(clusters):
        members = [r for r in dialogue_rows if r["cluster"] == cl]
        if not members:
            continue
        ag, aa, aconf = _cluster_evidence(members)

        # ភស្តុតាងអត្ថបទ (ឈ្មោះ · ពាក្យអាយុ)
        names = [m["name"] for m in members if m["name"]]
        if not names:                       # យកឈ្មោះពីបន្ទាត់ពិពណ៌នាមុន (បរិបទឆាក)
            first = members[0]["index"]
            for j in range(first - 1, max(-1, first - 4), -1):
                nm = C.name_in_line(texts[j], names_all)
                if nm and nm not in taken:
                    names = [nm]
                    break
        name = max(set(names), key=names.count) if names else ""
        roles = [m["role_text"] for m in members if m["role_text"] != C.NARR]
        role_text = max(set(roles), key=roles.count) if roles else ""

        # ---- ភេទ៖ សំឡេងមុន (អាទិភាព ១) · អត្ថបទជំនួយ ----
        text_gender = None
        if role_text in (C.F, C.OF, C.CH):
            text_gender = "female"
        elif role_text in (C.M, C.OM, C.CHM):
            text_gender = "male"
        elif name:
            p = C._profile(name)
            text_gender = "female" if p in (C.F, C.OF, C.CH) else "male" if p in (C.M, C.OM, C.CHM) else None

        source, conflict = "audio+text", False
        if aconf >= 0.5 and ag in ("male", "female"):
            gender = ag
            if text_gender and text_gender != ag:
                conflict = True
        elif text_gender:
            gender, source = text_gender, "text"
        else:
            gender, source = "unknown", "none"

        # ---- អាយុ៖ តួអង្គពីអត្ថបទ (មិនមែនពាក្យហៅ) > សំឡេង (ក្មេង) > ពេញវ័យ ----
        role_age = {C.OM: "elderly", C.OF: "elderly", C.CH: "child", C.CHM: "child"}
        age, age_src = None, ""
        if role_text in role_age:
            age, age_src = role_age[role_text], "text"
        if not age:
            for m in members:
                # ពាក្យបញ្ជាក់អាយុ "ក្រៅសម្រង់សម្ដី" ប៉ុណ្ណោះ (爷爷说… មិនមែន "爷爷，您…")
                raw = m["zh"]
                q2 = C.QUOTED.search(raw)
                outside2 = raw[:q2.start()] if q2 else raw
                if C._any(outside2, C.OLD):
                    age, age_src = "elderly", "text"
                    break
                if C._any(outside2, C.CHILD):
                    age, age_src = "child", "text"
                    break
                if C._any(outside2, TEEN_WORDS):
                    age, age_src = "teen", "text"
        if not age:
            if aa == "child":
                age, age_src = "child", "audio"
            elif aa == "elderly":
                age, age_src = "elderly", "audio"
            else:
                age, age_src = "adult", "default"
        # ភេទមិនដឹង + ក្មេង → មិនប្រឌិតភេទ (Test J)
        role = _role_code(gender, age)

        # ---- fingerprint (F0 + brightness) → តួអង្គដដែលឆ្លងឆាក ----
        f0s = sorted((m["audio"] or {}).get("f0") or 0 for m in members)
        f0s = [x for x in f0s if x > 0]
        zs = sorted((m["audio"] or {}).get("zcr") or 0 for m in members)
        fp_f0 = round(f0s[len(f0s) // 2], 1) if f0s else 0.0
        fp_zcr = round(zs[len(zs) // 2], 3) if zs else 0.0

        # ---- registry: តួអង្គដដែល? (ឈ្មោះ → fingerprint) ----
        prev_char = None
        if con is not None and pid:
            prev_char = R.find_by_name(con, pid, name) if name else None
            if not prev_char and fp_f0:
                prev_char = R.find_by_fingerprint(con, pid, fp_f0, fp_zcr, gender, age)
        elif previous:
            prev_char = next((c for c in previous if name and c.get("name") == name), None)

        corrected = ""
        if prev_char:
            cid = prev_char["id"]
            voice = prev_char.get("voice") or ""
            manual = (prev_char.get("assignment") == "manual") and not reassign
            info = V.info(voice) if voice else {}
            p_age = info.get("age") or ""
            # ភេទ/អាយុ ដែលការវិភាគថ្មីផ្តល់ឱ្យ → កែបញ្ជីចាស់ (ID ដដែល)
            if prev_char.get("gender") not in (None, "", gender) and gender != "unknown":
                corrected = "gender"
            if prev_char.get("age") not in (None, "", age) and age != "unknown":
                corrected = (corrected + "+age") if corrected else "age"
            # សំឡេងដែលមិនស៊ីនឹងភេទថ្មី (ខុសភេទ) → ត្រូវប្តូរ (លើកលែង manual)
            bad = (not voice
                   or info.get("gender") not in ("unknown", "", gender))
            if age != "unknown" and p_age and p_age not in (age, "unknown"):
                bad = True
            if reassign or (bad and not manual):
                voice = V.for_character(gender, age, used=used_voices)
            assignment = "manual" if manual else "automatic"
        else:
            voice = V.for_character(gender, age, used=used_voices)
            manual, assignment = False, "automatic"
            cid = _next_id(characters, con, pid)

        if voice not in used_voices:
            used_voices.append(voice)
        # voice book (ឈ្មោះដដែល = សំឡេងដដែល ឆ្លងភាគ)
        if name and voicebook and name in voicebook and not manual:
            voice = voicebook[name]
            if voice not in used_voices:
                used_voices.append(voice)

        if name:
            taken.add(name)
        by_cluster[cl] = cid
        char = {
            "id": cid, "name": name or (prev_char or {}).get("name") or f"តួអង្គ {_vname(ci)}",
            "gender": gender, "age": age, "role": role, "kind": "character",
            "cluster": cl, "conf": aconf if source.startswith("audio") else round(0.8 * (aconf or 0.6), 2),
            "lines": len(members), "voice": voice, "source": source,
            "assignment": assignment, "manual": manual,
            "voice_provider": provider,
            "named": bool(name) or bool((prev_char or {}).get("named")),
            "conflict": conflict, "age_source": age_src,
            "evidence": source, "color": COLOR_POOL[ci % len(COLOR_POOL)],
            "f0": fp_f0, "zcr": fp_zcr,
            # សំឡេងដែលបានជ្រើស មិនស៊ីនឹងភេទ/អាយុដែលបានវិភាគ (ត្រូវបង្ហាញក្នុង UI)
            "voice_mismatch": bool(voice and V.info(voice).get("gender") not in ("unknown", "", gender)),
            "corrected": corrected,
        }
        characters.append(char)
        if con is not None and pid:
            R.upsert_character(con, pid, {**char, "fp_f0": fp_f0, "fp_zcr": fp_zcr},
                               keep_voice=not reassign)

    # ---- បន្ទាត់ដែលគ្មានសំឡេង (ឬសំឡេងស្ងាត់) ----
    loose = [r for r in dialogue_rows if r["cluster"] is None]
    if loose:
        # បើអាចភ្ជាប់តាមឈ្មោះ → ភ្ជាប់ · បើអត់ → unknown (មិនប្រឌិតភេទ)
        unknown_id = None
        for r in loose:
            target = None
            if r["name"]:
                target = next((c for c in characters if c["name"] == r["name"]), None)
            if not target and r["role_text"] not in ("", C.NARR):
                target = next((c for c in characters if c["role"] == r["role_text"]), None)
            if not target:
                if not unknown_id:
                    unknown_id = "u1"
                    u = {
                        "id": unknown_id, "name": "មិនទាន់ដឹង", "gender": "unknown",
                        "age": "unknown", "role": "unknown", "kind": "unknown",
                        "cluster": None, "conf": 0.3, "lines": 0,
                        "voice": "unknown_1", "source": "none", "color": "#94a3b8",
                        "evidence": "none", "conflict": False, "assignment": "automatic",
                        "voice_provider": provider, "named": False,
                    }
                    characters.append(u)
                    if con is not None and pid:
                        R.upsert_character(con, pid, u)
                target = next(c for c in characters if c["id"] == unknown_id)
            target["lines"] += 1
            r["char_id"] = target["id"]

    # ---- ជំហាន ៣៖ ចាត់បន្ទាត់ → តួអង្គ ----
    items = []
    for r in rows:
        if r["role_text"] == C.NARR and narrator_id:
            cid = narrator_id
        elif r.get("char_id"):
            cid = r["char_id"]
        elif r["cluster"] is not None and r["cluster"] in by_cluster:
            cid = by_cluster[r["cluster"]]
        else:
            cid = next((c["id"] for c in characters if c["id"] == "u1"),
                       characters[-1]["id"] if characters else "u1")
        ch = next((c for c in characters if c["id"] == cid), None)
        # ភាពជឿជាក់បញ្ចូល
        aconf = 0.0
        if r["audio"]:
            aconf = D.voice_class(r["audio"])[2]
        conf = round(max(aconf, r["conf_text"] * 0.85), 2)
        items.append({
            "char_id": cid,
            "char": ch["role"] if ch else C.NARR,
            "conf": conf,
            "source": ("audio" if aconf >= 0.45 else "text") if ch else "none",
            "style": r["style"],
        })

    limits = []
    if not audio_segs:
        limits.append("គ្មានការវិភាគសំឡេង (វីដេអូគ្មានសំឡេង ឬមិនអាចអានបាន) — ប្រើតែអត្ថបទ")
    if any(c.get("conflict") for c in characters):
        limits.append("មានបន្ទាត់ដែលអត្ថបទផ្ទុយនឹងសំឡេង — យើងយកសំឡេងជាអាទិភាព")
    if any(c["age"] == "elderly" for c in characters):
        limits.append("edge-tts គ្មានសំឡេងខ្មែរចាស់ — បង្កើតដោយបន្ថយល្បឿន និងកម្ពស់សំឡេង")
    if any(c["age"] == "child" for c in characters):
        limits.append("edge-tts គ្មានសំឡេងខ្មែរក្មេង — បង្កើតដោយបង្កើនកម្ពស់សំឡេង")

    if con is not None and pid:
        R.ensure_project(con, pid, video_id)
        R.save_segments(con, pid, [
            {"idx": i, "cid": it["char_id"],
             "voice_id": next((c["voice"] for c in characters if c["id"] == it["char_id"]), None),
             "start": (lines[i].get("start") if i < len(lines) else None),
             "end": (lines[i].get("end") if i < len(lines) else None),
             "zh": (lines[i].get("zh") if i < len(lines) else None)}
            for i, it in enumerate(items)])

    return {
        "video_id": video_id,
        "project": pid or video_id,
        "characters": characters,
        "items": items,
        "scenes": (audio or {}).get("scenes") or [],
        "summary": _summary(characters),
        "limitations": limits,
        "audio": {
            "speakers": (audio or {}).get("speakers", 0),
            "analysed": len(audio_segs),
        },
    }


def _next_id(characters, con=None, pid=None):
    """ID ថ្មីដែលមិនជាន់ (c1, c2, …) — តួអង្គចាស់រក្សា ID ដើម"""
    used = {c["id"] for c in characters}
    if con is not None and pid:
        used |= {c["id"] for c in R.characters(con, pid)}
    i = 1
    while f"c{i}" in used:
        i += 1
    return f"c{i}"


def _role_code(gender, age):
    if age == "elderly":
        return C.OF if gender == "female" else C.OM
    if age == "child":
        return C.CH if gender == "female" else C.CHM
    if age == "teen":
        return C.F if gender == "female" else C.M
    if gender == "female":
        return C.F
    if gender == "male":
        return C.M
    return "unknown"


def _summary(chars):
    parts = []
    for c in chars:
        if c.get("kind") == "narrator":
            parts.append(f"📖 {c['lines']}")
            continue
        icon = {"male": "👨", "female": "👩", "unknown": "❔"}.get(c["gender"], "👤")
        age = {"child": "🧒", "elderly": "👴" if c["gender"] != "female" else "👵",
               "teen": "🧑"}.get(c["age"], "")
        parts.append(f"{icon}{age} {c['name']} {c['lines']}")
    return " · ".join(parts)


# ---------- រក្សាទុក ----------
def save_cast(store, video_id, data):
    try:
        p = store / f"{video_id}.cast.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        return p
    except Exception as e:
        print("save cast failed:", e, flush=True)
        return None


def load_cast(store, video_id):
    try:
        p = store / f"{video_id}.cast.json"
        if p.exists():
            return json.loads(p.read_text())
    except Exception as e:
        print("load cast failed:", e, flush=True)
    return None


def voicebook_path(store):
    return store / "voicebook.json"


def load_voicebook(store):
    try:
        p = voicebook_path(store)
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return {}


def save_voicebook(store, book):
    try:
        voicebook_path(store).write_text(json.dumps(book, ensure_ascii=False))
    except Exception as e:
        print("save voicebook failed:", e, flush=True)


def bind_voicebook(store, characters):
    """ឈ្មោះតួអង្គ (មិនមែន id) → voice ថេរ ពេញរឿង និងឆ្លងភាគ"""
    book = load_voicebook(store)
    changed = False
    for c in characters:
        n = c.get("name")
        if not n or c.get("kind") != "character" or not c.get("named", True):
            continue
        if n in book:
            c["voice"] = book[n]
        else:
            book[n] = c["voice"]
            changed = True
    if changed:
        save_voicebook(store, book)
    return book


def apply_overrides(data, overrides):
    """ការជ្រើសដោយដៃ → ឈ្នះស្វ័យប្រវត្តិ ជារៀងរហូត (រហូតដល់ reset)"""
    overrides = overrides or {}
    for c in data.get("characters", []):
        v = overrides.get(c["id"])
        if v and v in V.VOICES:
            c["voice"] = v
            c["manual"] = True
            c["source"] = "manual"
    return data
