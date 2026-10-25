"""Character & voice registry — SQLite ជាប់ជាអចិន្ត្រៃយ៍ (persistent)

ហេតុអ្វីត្រូវការ៖ តួអង្គម្នាក់ត្រូវរក្សា **ID** និង **សំឡេង** ដដែលពេញរឿង និងឆ្លងការ
restart របស់ backend / reload គម្រោង / បង្កើតអត្ថបទឡើងវិញ។

តារាង៖
  projects  (pid, video, created, updated)
  characters(cid, pid, name, gender, age, role, voice_provider, voice_id,
             assignment, conf, fp_f0, fp_zcr, first_seen, last_seen)
  segments  (pid, idx, cid, voice_id, start, end, zh, km)

ការជ្រើសតួអង្គ៖
  1. ឈ្មោះដូចគ្នា (ក្នុងគម្រោងតែមួយ) → តួអង្គដដែល
  2. មិនមានឈ្មោះ → ធៀប fingerprint (F0 + brightness) → តួអង្គដដែល
  3. មិនដូច → បង្កើត ID ថ្មី (គ្រាន់តែពេលជាតួអង្គថ្មីពិតប្រាកដ)
"""

import json
import pathlib
import sqlite3
import time
import uuid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  pid TEXT PRIMARY KEY, video TEXT, created TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS characters (
  cid TEXT PRIMARY KEY, pid TEXT NOT NULL, name TEXT,
  gender TEXT, age TEXT, role TEXT,
  voice_provider TEXT, voice_id TEXT, auto_voice TEXT, assignment TEXT,
  conf REAL, fp_f0 REAL, fp_zcr REAL, named INTEGER DEFAULT 0,
  first_seen TEXT, last_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_char_pid ON characters(pid);
CREATE TABLE IF NOT EXISTS segments (
  pid TEXT NOT NULL, idx INTEGER NOT NULL, cid TEXT, voice_id TEXT,
  start REAL, end REAL, zh TEXT, km TEXT, audio TEXT,
  PRIMARY KEY (pid, idx)
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


def db_path(data_dir):
    return pathlib.Path(data_dir) / "kh_drama.db"


def connect(data_dir):
    p = db_path(data_dir)
    con = sqlite3.connect(str(p), timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    cols = {r[1] for r in con.execute("PRAGMA table_info(characters)")}
    if "auto_voice" not in cols:        # migration សម្រាប់ DB ចាស់
        con.execute("ALTER TABLE characters ADD COLUMN auto_voice TEXT")
        con.commit()
    return con


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------- projects ----------
def ensure_project(con, pid, video=""):
    con.execute("INSERT INTO projects(pid, video, created, updated) VALUES(?,?,?,?) "
                "ON CONFLICT(pid) DO UPDATE SET video=excluded.video, updated=excluded.updated",
                (pid, video, _now(), _now()))
    con.commit()


# ---------- characters ----------
def _norm_voice(v):
    """voice ចាស់ → សំឡេងធម្មតា (Piseth/Sreymom) តាមភេទ · ភេទមិនប្តូរ"""
    try:
        from .voices import normalize
        return normalize(v)
    except Exception:
        return v


def _row_to_char(r):
    return {
        "id": r["cid"], "name": r["name"] or "", "gender": r["gender"] or "unknown",
        "age": r["age"] or "unknown", "role": r["role"] or "unknown",
        "voice_provider": r["voice_provider"], "voice": _norm_voice(r["voice_id"]),
        "auto_voice": _norm_voice(r["auto_voice"]) if "auto_voice" in r.keys() else None,
        "assignment": r["assignment"] or "automatic", "manual": (r["assignment"] == "manual"),
        "conf": r["conf"] if r["conf"] is not None else 0.5,
        "named": bool(r["named"]), "fp_f0": r["fp_f0"], "fp_zcr": r["fp_zcr"],
        "first_seen": r["first_seen"], "last_seen": r["last_seen"],
    }


def characters(con, pid):
    return [_row_to_char(r) for r in con.execute(
        "SELECT * FROM characters WHERE pid=? ORDER BY first_seen, cid", (pid,))]


def find_by_name(con, pid, name):
    if not name:
        return None
    r = con.execute("SELECT * FROM characters WHERE pid=? AND name=?", (pid, name)).fetchone()
    return _row_to_char(r) if r else None


def find_by_fingerprint(con, pid, f0, zcr, gender, age, tol_f0=0.12, tol_zcr=0.06):
    """តួអង្គដែលមានសំឡេងដូចគ្នា (ឆ្លងឆាក) — មិនបង្កើត ID ថ្មីឥតប្រយោជន៍

    បើភេទ/អាយុ ខុសគ្នា តែសំឡេងដូចគ្នាខ្លាំង (tol តឹង) → យកតួអង្គដើម
    (បង្ហាញថា ការសន្និដ្ឋានភេទ/អាយុ ត្រូវកែ មិនមែនបង្កើតតួអង្គថ្មី)។
    """
    if not f0:
        return None
    best, best_d = None, 9e9
    for c in characters(con, pid):
        if not c.get("fp_f0"):
            continue
        d_f0 = abs(c["fp_f0"] - f0) / max(1.0, f0)
        d_z = abs((c.get("fp_zcr") or 0) - (zcr or 0))
        same = (c["gender"] == gender and c["age"] == age)
        lim_f0, lim_z = (tol_f0, tol_zcr) if same else (0.05, 0.025)
        if d_f0 <= lim_f0 and d_z <= lim_z:
            d = d_f0 + d_z + (0 if same else 0.5)
            if d < best_d:
                best, best_d = c, d
    return best


def upsert_character(con, pid, char, keep_voice=True):
    """បញ្ចូល/ធ្វើបច្ចុប្បន្នភាពតួអង្គ — រក្សា ID និងសំឡេងចាស់ (បើមិន manual)"""
    cid = char.get("id") or f"c_{uuid.uuid4().hex[:8]}"
    old = con.execute("SELECT * FROM characters WHERE cid=?", (cid,)).fetchone()
    now = _now()
    if old:
        o = _row_to_char(old)
        manual = (o["assignment"] == "manual") and keep_voice
        voice = o["voice"] if manual else char.get("voice", o["voice"])
        provider = o["voice_provider"] if manual else char.get("voice_provider", o["voice_provider"])
        auto = o.get("auto_voice") or (o["voice"] if o["assignment"] != "manual" else None)
        if not manual:
            auto = voice
        assignment = "manual" if manual else "automatic"
        con.execute("""UPDATE characters SET name=?, gender=?, age=?, role=?, voice_provider=?,
                       voice_id=?, auto_voice=?, assignment=?, conf=?, fp_f0=?, fp_zcr=?, named=?, last_seen=?
                       WHERE cid=?""",
                    (char.get("name") or o["name"], char.get("gender") or o["gender"],
                     char.get("age") or o["age"], char.get("role") or o["role"],
                     provider, voice, auto, assignment, char.get("conf", o["conf"]),
                     char.get("fp_f0", o["fp_f0"]), char.get("fp_zcr", o["fp_zcr"]),
                     1 if char.get("named") else (1 if o["named"] else 0), now, cid))
    else:
        con.execute("""INSERT INTO characters(cid, pid, name, gender, age, role, voice_provider,
                       voice_id, auto_voice, assignment, conf, fp_f0, fp_zcr, named, first_seen, last_seen)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (cid, pid, char.get("name", ""), char.get("gender", "unknown"),
                     char.get("age", "unknown"), char.get("role", "unknown"),
                     char.get("voice_provider", ""), char.get("voice", ""),
                     char.get("voice", ""),
                     char.get("assignment", "automatic"), char.get("conf", 0.5),
                     char.get("fp_f0") or 0.0, char.get("fp_zcr") or 0.0,
                     1 if char.get("named") else 0, now, now))
    con.commit()
    return cid


def set_voice(con, cid, voice_id, provider="", manual=True):
    """manual=True → កត់ត្រា auto_voice ដើម ដើម្បី reset បានត្រឡប់មកវិញ"""
    r = con.execute("SELECT voice_id, auto_voice, assignment FROM characters WHERE cid=?", (cid,)).fetchone()
    auto = None
    if r:
        auto = r["auto_voice"] or (r["voice_id"] if r["assignment"] != "manual" else None)
    if manual:
        con.execute("UPDATE characters SET voice_id=?, voice_provider=?, auto_voice=?, assignment=?, "
                    "last_seen=? WHERE cid=?",
                    (voice_id, provider, auto, "manual", _now(), cid))
    else:
        con.execute("UPDATE characters SET voice_id=?, voice_provider=?, auto_voice=?, assignment=?, "
                    "last_seen=? WHERE cid=?",
                    (voice_id, provider, voice_id, "automatic", _now(), cid))
    con.commit()


def reset_manual(con, pid):
    """Reset → ត្រឡប់ទៅសំឡេងស្វ័យប្រវត្តិដើម (មិនរក្សាសំឡេងជ្រើសដោយដៃ)"""
    con.execute("UPDATE characters SET assignment='automatic', "
                "voice_id=COALESCE(auto_voice, voice_id) WHERE pid=?", (pid,))
    con.commit()


def delete_character(con, cid):
    con.execute("DELETE FROM characters WHERE cid=?", (cid,))
    con.commit()


# ---------- segments ----------
def save_segments(con, pid, rows):
    """rows: [{idx, cid, voice_id, start, end, zh, km, audio}]"""
    con.executemany(
        "INSERT INTO segments(pid, idx, cid, voice_id, start, end, zh, km, audio) "
        "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(pid, idx) DO UPDATE SET "
        "cid=COALESCE(excluded.cid, segments.cid), voice_id=COALESCE(excluded.voice_id, segments.voice_id), "
        "start=excluded.start, end=excluded.end, zh=COALESCE(excluded.zh, segments.zh), "
        "km=COALESCE(excluded.km, segments.km), audio=COALESCE(excluded.audio, segments.audio)",
        [(pid, r["idx"], r.get("cid"), r.get("voice_id"), r.get("start"), r.get("end"),
          r.get("zh"), r.get("km"), r.get("audio")) for r in rows])
    con.commit()


def segments(con, pid):
    rows = [dict(r) for r in con.execute("SELECT * FROM segments WHERE pid=? ORDER BY idx", (pid,))]
    for r in rows:
        r["voice_id"] = _norm_voice(r.get("voice_id"))
    return rows


def set_segment_voice(con, pid, idx, cid, voice_id, audio=None):
    con.execute("UPDATE segments SET cid=?, voice_id=?, audio=COALESCE(?, audio) WHERE pid=? AND idx=?",
                (cid, voice_id, audio, pid, idx))
    con.commit()


def delete_project(con, pid):
    con.execute("DELETE FROM characters WHERE pid=?", (pid,))
    con.execute("DELETE FROM segments WHERE pid=?", (pid,))
    con.execute("DELETE FROM projects WHERE pid=?", (pid,))
    con.commit()


# ---------- helpers ----------
def project_state(con, pid):
    """ស្ថានភាពពេញលេញ (ផ្ទុកឡើងវិញក្រោយ restart — Test 9)"""
    proj = con.execute("SELECT * FROM projects WHERE pid=?", (pid,)).fetchone()
    return {
        "project": pid,
        "video": proj["video"] if proj else None,
        "updated": proj["updated"] if proj else None,
        "characters": characters(con, pid),
        "segments": segments(con, pid),
    }


def export_manifest(con, pid):
    """សម្រាប់ Test 10៖ បន្ទាត់នីមួយៗ → តួអង្គ + សំឡេង ដែលបានបង្កើតពិត"""
    chars = {c["id"]: c for c in characters(con, pid)}
    out = []
    for s in segments(con, pid):
        c = chars.get(s["cid"]) or {}
        out.append({
            "index": s["idx"], "start": s["start"], "end": s["end"],
            "char_id": s["cid"], "char_name": c.get("name"),
            "gender": c.get("gender"), "age": c.get("age"),
            "voice_expected": c.get("voice"), "voice_used": s["voice_id"],
            "audio": s.get("audio"),
            "match": bool(c.get("voice") and s["voice_id"] == c.get("voice")),
        })
    return {"project": pid, "segments": out,
            "ok": all(x["match"] for x in out) if out else False,
            "characters": list(chars.values())}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)
