import subprocess, uuid, pathlib, zipfile, sys, shutil, json, os, time
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import providers as P
from . import subs as SB
from . import graph as G
from . import cast as C
from . import diarize as D
from . import segments as SG
from . import identity as ID
from . import voices as V
from . import registry as RG
from . import encode as E
from . import progress as PR

from .paths import ROOT, STORE, DATA   # exe: STORE ក្នុង folder អ្នកប្រើ

app = FastAPI(title="KH Drama Studio AI")


def reg():
    """SQLite registry (តួអង្គ + សំឡេង ថេរ ឆ្លង restart)"""
    return RG.connect(DATA)

def ff(*a):
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error", *a], capture_output=True, text=True, cwd=STORE)   # cwd=storage → ឈ្មោះ file សាមញ្ញ
    if r.returncode: raise RuntimeError("FFmpeg: " + r.stderr[-1500:])
def guard(fn):
    try: return fn()
    except KeyError as e: raise HTTPException(400, f"បាត់ API Key ឬការកំណត់: {e}")
    except Exception as e: raise HTTPException(500, str(e))

@app.get("/api/catalog")
def catalog(): return P.CATALOG
@app.get("/api/tiers")
def tiers(): return {"tiers": P.TIERS, "current": P.tier(P.load())}
@app.get("/api/settings")
def get_settings(): return P.masked(P.load())
@app.post("/api/settings")
def set_settings(d: dict):
    if "tier" in d and d["tier"] not in P.TIERS: raise HTTPException(400, "tier មិនត្រឹមត្រូវ")
    cur = P.load(); cur.update({k: v for k, v in d.items() if v and not str(v).startswith("••••")}); P.save(cur); return {"ok": True}

@app.post("/api/upload")
async def upload(file: UploadFile):
    vid = uuid.uuid4().hex[:10]
    (STORE / f"{vid}.mp4").write_bytes(await file.read())
    return {"id": vid, "url": f"/files/{vid}.mp4"}

class Vid(BaseModel): id: str
@app.post("/api/transcribe")
def transcribe(b: Vid):
    """STT → បន្ថែម char (តួអង្គ) ដោយ auto-scan ឥតគិតថ្លៃ (rule based)"""
    mp3 = STORE / f"{b.id}.mp3"
    def run():
        ff("-i", str(STORE / f"{b.id}.mp4"), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(mp3))
        segs = P.stt(mp3, P.load())
        # កាត់បន្ទាត់វែង (ឧ. 5.3 → 41.0) តាមសំឡេងពិត — គ្មានឃ្លាលើស ៨ វិនាទី
        segs = SG.fit(segs, mp3)
        scan = C.scan([s.get("zh", "") for s in segs])   # តួអង្គស្វ័យប្រវត្តិ
        for s, it in zip(segs, scan["items"]):
            s["char"] = it["char"]; s["conf"] = it["conf"]
        return segs
    return guard(run)

class FixLines(BaseModel):
    id: str = ""
    segments: list[dict] = []


@app.post("/api/segments/fix")
def segments_fix(b: FixLines):
    """កាត់បន្ទាត់វែងក្នុងគម្រោងដែលមានស្រាប់ (មិនចាំបាច់ Transcribe ម្តងទៀត)

    ប្រើសំឡេងពិតរបស់វីដេអូ → កាត់ត្រង់ចន្លោះស្ងាត់ · គ្មានបន្ទាត់លើស ៨ វិនាទី។
    """
    name = pathlib.Path(b.id).name if b.id else ""
    audio = None
    for ext in ("mp4", "mp3", "wav", "m4a"):
        if name and (STORE / f"{name}.{ext}").exists():
            audio = STORE / f"{name}.{ext}"
            break
    segs = [s for s in b.segments if isinstance(s, dict)]
    out = SG.fit(segs, str(audio) if audio else None)
    return {"segments": out, "count": len(out), "audio": bool(audio)}


class CastIn(BaseModel):
    lines: list[str]
    keep: list[str] = []   # char ដែលអ្នកប្រើកែដោយដៃ → រក្សាទុក
@app.post("/api/cast")
def cast_scan(b: CastIn):
    """ស្កេនតួអង្គពីអត្ថបទចិន (ឥតគិតថ្លៃ · មិនត្រូវការ key)"""
    return C.scan(b.lines, keep=b.keep)

@app.get("/api/characters")
def characters(id: str = ""):
    """បញ្ជីតួអង្គ + សំឡេង · បើផ្តល់ id → ត្រឡប់ cast ដែលបានរក្សាទុក"""
    out = []
    for c in C.CHARS:
        (gender, rate, pitch, volume), _ = P.char_profile(c)
        out.append({"char": c, "label": C.LABELS[c], "color": C.COLORS[c],
                    "voice": gender, "rate": rate, "pitch": pitch, "volume": volume,
                    "voiceName": P.VOICE_LABEL.get(c, gender)})
    data = {"roles": out, "default": C.NARR, "voices": V.all_for_ui(),
            "ages": V.AGE_LABEL, "genders": V.GENDER_LABEL,
            "style": "natural" if V.NATURAL else "varied",
            "limitations": ([
                "សំឡេងធម្មតា — Piseth (ប្រុស) និង Sreymom (ស្រី) ដូចដើម · គ្មានកែ pitch/rate",
                "ភេទមិនដែលប្តូរ — តួអង្គស្រីទាំងអស់ប្រើ Sreymom · ប្រុសទាំងអស់ប្រើ Piseth",
            ] if V.NATURAL else [
                "edge-tts (ឥតគិតថ្លៃ) មានសំឡេងខ្មែរតែ ២ (Piseth ប្រុស · Sreymom ស្រី) — ចាស់/ក្មេង/តួប្រុស ២ នាក់ បង្កើតដោយ rate · pitch · volume",
                "បើកំណត់ Azure/Google/ElevenLabs ក្នុង Settings នឹងប្រើសំឡេងពិតរបស់ពួកគេ",
            ])}
    if id:
        data["cast"] = ID.load_cast(STORE, id)
    return data


class DetectIn(BaseModel):
    id: str
    segments: list[dict] = []      # [{start,end,zh}]
    use_audio: bool = True
    voicebook: bool = True
    project: str = ""              # គម្រោង (លំនាំដើម = id)
    reassign: bool = False         # ចាត់សំឡេងឡើងវិញទាំងអស់


@app.post("/api/characters/detect")
def characters_detect(b: DetectIn):
    """វិភាគតួអង្គពី សំឡេង + អត្ថបទ → ID ថេរ + សំឡេងថេរ (រក្សាក្នុង SQLite)"""
    def run():
        segs = [s for s in b.segments if isinstance(s, dict)]
        pid = b.project or b.id
        audio = None
        video = STORE / f"{b.id}.mp4"
        if b.use_audio and video.exists() and segs:
            try:
                audio = D.analyze_segments(video, segs)
            except Exception as e:
                print("diarization failed:", e, flush=True)
                audio = None
        con = reg()
        try:
            prev = RG.project_state(con, pid)
            book = ID.load_voicebook(STORE) if b.voicebook else {}
            sup = P.voice_support_report()
            res = ID.resolve(segs, audio, video_id=b.id, voicebook=book,
                             previous=prev.get("characters"), con=con, pid=pid,
                             provider=sup["provider"], reassign=bool(b.reassign))
            if b.voicebook:
                ID.bind_voicebook(STORE, res["characters"])
            res["provider"] = sup
            res["limitations"] = list(dict.fromkeys(res.get("limitations", []) + sup["limitations"]))
            RG.ensure_project(con, pid, b.id)
            ID.save_cast(STORE, b.id, res)     # fallback ពេល TTS គ្មាន row ក្នុង DB
            return res
        finally:
            con.close()
    return guard(run)


class AssignIn(BaseModel):
    id: str
    overrides: dict = {}           # {char_id: voice_id}
    reset: bool = False
    project: str = ""


@app.post("/api/characters/assign")
def characters_assign(b: AssignIn):
    """ជ្រើសសំឡេងដោយដៃ → រក្សាក្នុង registry ជារៀងរហូត (រហូតដល់ reset)"""
    def run():
        pid = b.project or b.id
        con = reg()
        try:
            if b.reset:
                RG.reset_manual(con, pid)
            changed_voice_ids = []
            current_chars = {c["id"]: c for c in RG.characters(con, pid)}
            provider = P.voice_support_report()["provider"]
            cached = ID.load_cast(STORE, pathlib.Path(b.id).name) or {}
            cached_chars = {c.get("id"): c for c in cached.get("characters", []) if c.get("id")}
            id_map, overrides = {}, {}
            # ផ្ទៀងផ្ទាត់ ID និង voice មុន restore ដើម្បីកុំឱ្យ request មិនត្រឹមត្រូវកែ DB មួយផ្នែក។
            for cid, vid in (b.overrides or {}).items():
                if vid not in V.VOICES:
                    raise HTTPException(400, f"សំឡេងមិនស្គាល់: {vid}")
                if cid not in current_chars and cid not in cached_chars:
                    raise HTTPException(404, f"រកមិនឃើញតួអង្គ: {cid}")
            # កែសង្គ្រោះ cast ចាស់ដែលមានក្នុង JSON តែបាត់ពី registry (ឧ. narrator ជាន់ ID គម្រោងផ្សេង)។
            for cid, vid in (b.overrides or {}).items():
                target = cid
                if target not in current_chars and cid in cached_chars:
                    target = RG.ensure_project_character(con, pid, cached_chars[cid])
                    current_chars = {c["id"]: c for c in RG.characters(con, pid)}
                    if target != cid:
                        id_map[cid] = target
                overrides[target] = vid
            # ផ្ទៀងផ្ទាត់ទាំងអស់មុនកែ ដើម្បីកុំឱ្យ Apply All បានលទ្ធផលតែពាក់កណ្ដាល។
            for cid in overrides:
                if cid not in current_chars:
                    raise HTTPException(404, f"រកមិនឃើញតួអង្គ: {cid}")
            for cid, vid in overrides.items():
                if current_chars[cid].get("voice") != vid:
                    changed_voice_ids.append(cid)
                RG.set_voice(con, cid, vid, provider=provider, manual=True)
            # voice book: ឈ្មោះ → សំឡេង (ឆ្លងភាគ)
            book = ID.load_voicebook(STORE)
            if b.reset:
                chars = RG.characters(con, pid)
                for c in chars:
                    if c.get("named") and c.get("name"):
                        book.pop(c["name"], None)
            else:
                for c in RG.characters(con, pid):
                    if c.get("assignment") == "manual" and c.get("named") and c.get("name"):
                        book[c["name"]] = c["voice"]
            ID.save_voicebook(STORE, book)
            # ធ្វើបច្ចុប្បន្នភាព segment តាមសំឡេងថ្មី
            chars = {c["id"]: c for c in RG.characters(con, pid)}
            rows = [{"idx": s["idx"], "cid": s["cid"], "voice_id": (chars.get(s["cid"]) or {}).get("voice"),
                     "start": s["start"], "end": s["end"], "zh": s["zh"]}
                    for s in RG.segments(con, pid)]
            if rows:
                RG.save_segments(con, pid, rows)
            RG.clear_character_segment_audio(con, pid, changed_voice_ids)
            result_chars = RG.characters(con, pid)
            if id_map and cached:
                by_id = {c["id"]: c for c in result_chars}
                for c in cached.get("characters", []):
                    c["id"] = id_map.get(c.get("id"), c.get("id"))
                    saved = by_id.get(c["id"])
                    if saved:
                        c.update({k: saved.get(k) for k in ("voice", "assignment", "manual", "voice_provider")})
                for item in cached.get("items", []):
                    item["char_id"] = id_map.get(item.get("char_id"), item.get("char_id"))
                ID.save_cast(STORE, pathlib.Path(b.id).name, cached)
            return {"ok": True, "characters": result_chars, "id_map": id_map,
                    "overrides": {c["id"]: c["voice"] for c in result_chars
                                  if c.get("assignment") == "manual"}}
        finally:
            con.close()
    return guard(run)


@app.get("/api/project/{pid}")
def project_state(pid: str):
    """ផ្ទុកគម្រោងឡើងវិញ (ក្រោយ restart / reload) — Test 9"""
    con = reg()
    try:
        st = RG.project_state(con, pid)
        st["provider"] = P.voice_support_report()
        return st
    finally:
        con.close()


@app.get("/api/export_manifest")
def export_manifest(id: str):
    """manifest៖ សំឡេងដែលប្រើក្នុង export ត្រូវនឹងសំឡេងតួអង្គឬទេ"""
    con = reg()
    try:
        man = RG.export_manifest(con, id)
        p = STORE / f"{id}.voices.json"
        if p.exists():
            man["export"] = (json.loads(p.read_text()) or {}).get("export")
        return man
    finally:
        con.close()


class PreviewIn(BaseModel):
    voice: str
    text: str = "សួស្តី ខ្ញុំសាកល្បងសំឡេងនេះ។"


@app.post("/api/voice_preview")
def voice_preview(b: PreviewIn):
    """សាកស្តាប់សំឡេង (សម្រាប់ប៊ូតុង 🔊 ក្នុងប្រអប់ Character)"""
    if b.voice not in V.VOICES and b.voice not in C.CHARS:
        raise HTTPException(400, "សំឡេងមិនត្រឹមត្រូវ")
    def run():
        name = f"preview_{uuid.uuid4().hex[:8]}.mp3"
        (STORE / name).write_bytes(P.tts(b.text[:200], b.voice, 0.0, P.load()))
        return {"url": f"/files/{name}", "voice": b.voice}
    try:
        return run()
    except Exception as e:
        raise HTTPException(503, f"បង្កើតសំឡេងសាកល្បងមិនបាន (ពិនិត្យ internet/key): {e}")

class Tr(BaseModel): lines: list[str]
@app.post("/api/translate")
def translate(b: Tr): return guard(lambda: P.translate(b.lines, P.load()))

class Sp(BaseModel):
    text: str
    char: str = ""          # role code ឬ voice id
    char_id: str = ""       # character id (registry)
    video: str = ""         # video/project id
    idx: int = -1           # segment index (សម្រាប់ manifest)
    gender: str = "male"    # តម្លៃចាស់ (backward compat)
    speed: float = 0.0


def _voice_for(b):
    """char_id → voice ពី registry (SQLite) — បើគ្មាន → cast json → role code → ភេទ

    គោលការណ៍៖ ភេទមិនដែលប្តូរ។ បើគ្មាន voice ក្នុង DB/cast → ប្រើ role code
    (男主/女主/旁白 …) ឬ ភេទដែលផ្ញើមក → ត្រឡប់ voice id ពិត (male_adult_1 / female_adult_1)
    ដើម្បីឱ្យ Piseth/Sreymom ត្រូវនឹងភេទរបស់បន្ទាត់។
    """
    if b.video:
        pid = b.video
        cid = b.char_id
        try:
            con = reg()
            try:
                if not cid and b.idx >= 0:
                    # frontend មិនបានផ្ញើ char_id → ប្រើតួអង្គដែលរក្សាទុករបស់ segment នេះ
                    rows = RG.segments(con, pid)
                    if 0 <= b.idx < len(rows):
                        cid = (rows[b.idx].get("cid") or "").strip()
                if cid:
                    for c in RG.characters(con, pid):
                        if c.get("id") == cid and c.get("voice"):
                            return V.normalize(c["voice"])
            finally:
                con.close()
        except Exception as e:
            print("registry lookup failed:", e, flush=True)
    if b.video and b.char_id:
        data = ID.load_cast(STORE, b.video) or {}
        for c in data.get("characters", []):
            if c.get("id") == b.char_id:
                if c.get("voice"):
                    return V.normalize(c["voice"])
                if c.get("gender") in ("male", "female"):     # cast json គ្មាន voice
                    return V.for_character(c["gender"], c.get("age") or "adult")
    char = (b.char or "").strip()
    if char in V.VOICES:                       # ជា voice id ស្រាប់
        return V.normalize(char)
    if char:                                   # ជា role code (男主/女主/旁白 …)
        try:
            from .cast import normalize as _cnorm
            code = _cnorm(char)
        except Exception:
            code = char
        prof = P.CHAR_VOICES.get(code)
        if prof and prof[0] in ("male", "female"):
            return V.for_character(prof[0], "adult")     # 男主→Piseth · 女主→Sreymom
    g = str(b.gender or "").strip().lower()
    if g in ("male", "female"):
        return V.for_character(g, "adult")
    return "unknown_1"


@app.post("/api/tts")
def tts(b: Sp):
    """បង្កើតសំឡេងខ្មែរ **តាមតួអង្គដែលបានរក្សាទុក** (Test 8: regenerate → voice ដដែល)"""
    def run():
        name = f"{uuid.uuid4().hex[:10]}.mp3"
        voice = _voice_for(b)
        (STORE / name).write_bytes(P.tts(b.text, voice, b.speed, P.load()))
        # កត់ត្រា៖ segment នេះប្រើសំឡេងអ្វី (សម្រាប់ manifest + Test 10)
        if b.video and b.idx >= 0:
            try:
                con = reg()
                try:
                    RG.set_segment_voice(con, b.video, b.idx, b.char_id or None, voice, f"/files/{name}")
                finally:
                    con.close()
            except Exception as e:
                print("record segment voice failed:", e, flush=True)
        return {"url": f"/files/{name}", "char": P.voice_profile(voice)[1], "voice": voice,
                "char_id": b.char_id or None, "idx": b.idx}
    return guard(run)


@app.get("/api/voices")
def voices_info(refresh: bool = False):
    """សំឡេងពិតរបស់ provider + ដែនកំណត់ (មិនប្រឌិត voice id)"""
    return P.voice_support_report(P.load()) if not refresh else P.voice_support_report(
        {**P.load(), "_refresh": True})


@app.post("/api/voices/refresh")
def voices_refresh():
    return P.voice_support_report(P.load())


def _q(q, quality, src):
    q = dict(q)
    if quality == "hd":
        # រក្សា preset របស់ tier (កុំធ្វើឱ្យយឺត) តែបង្កើនគុណភាពបន្តិច
        q.update(crf=min(int(q.get("crf", 20)), 21), abr="192k", hd=True)
        try:
            r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(STORE / src)], capture_output=True, text=True)
            w, h = [int(x) for x in r.stdout.strip().split(",")[:2]]
            if min(w, h) < 1080:
                k = 1080 / min(w, h)
                q["tw"], q["th"] = int(round(w * k / 2)) * 2, int(round(h * k / 2)) * 2
        except Exception as e:
            print("probe failed:", e, flush=True)
    return q

def _layers(b):
    """Khmer Text (data URL) → PNG, រៀប layer តាមលំដាប់ Logo→Sponsor→Overlay→Text"""
    G.prepare(STORE, b.id, b.layers)
    return G.layer_inputs(STORE, b.layers), [bx for bx in (b.boxes or []) if isinstance(bx, dict)]

class Ex(BaseModel):
    id: str; segments: list[dict]; subs: bool = True; blank: str = ""; bgm: str = ""; quality: str = ""
    speed: str = ""           # "fast" = លឿនបំផុត (veryfast/crf23) · "" = តាម tier
    layers: list[dict] = []   # [{kind, file|data, x, y, size, opacity}] — Logo / Sponsor / Overlay / Khmer Text
    boxes: list[dict] = []    # [{x,y,w,h,strength,start,end,follow,kf}] — Blur

def _fast(q):
    """របៀបលឿនបំផុត៖ preset លឿន + crf ខ្ពស់បន្តិច (ភ្នែកមើលស្ទើរមិនឃើញខុស)"""
    q = dict(q); q.update(preset="veryfast", crf=max(22, int(q.get("crf", 20)) + 3), abr="160k")
    return q

@app.post("/api/export")
def export(b: Ex):
    """Export ទាំងអស់ក្នុង pass តែមួយ: អក្សរខ្មែរ + សំឡេង + BGM + Layer + Blur

    ដំណើរការជា background job (ដើម្បីបង្ហាញ progress) → {"job": true}
    បន្ទាប់មក poll `GET /api/export_status?id=...` រហូត state = done|error
    """
    vid = pathlib.Path(b.id).name
    cur = PR.JOBS.get(vid) or {}
    if cur.get("state") == "running":
        raise HTTPException(409, "កំពុង Export វីដេអូនេះ — សូមរង់ចាំ")
    src, out, srt = STORE / f"{vid}.mp4", STORE / f"{vid}_km.mp4", STORE / f"{vid}.srt"
    t = lambda s: f"{int(s//3600):02}:{int(s%3600//60):02}:{int(s%60):02},{int(s*1000)%1000:03}"
    srt.write_text("\n".join(f"{i+1}\n{t(s['start'])} --> {t(s['end'])}\n{s['km']}\n" for i, s in enumerate(b.segments)), encoding="utf-8")
    clips = [s for s in b.segments if s.get("audio")]
    if not clips: raise HTTPException(400, "សូមចុច Generate Khmer Audio ជាមុន")
    # កត់ត្រា manifest៖ បន្ទាត់ → តួអង្គ → សំឡេង ដែលបានបង្កើតពិត (Test 10)
    try:
        con = reg()
        try:
            rows = []
            for i, sg in enumerate(b.segments):
                if not sg.get("audio"):
                    continue
                rows.append({"idx": i, "cid": sg.get("char_id"), "voice_id": sg.get("voice"),
                             "start": sg.get("start"), "end": sg.get("end"),
                             "zh": sg.get("zh"), "km": sg.get("km"), "audio": sg.get("audio")})
            if rows:
                RG.ensure_project(con, vid, vid)
                RG.save_segments(con, vid, rows)
            man = RG.export_manifest(con, vid)
            man["export"] = out.name
            (STORE / f"{vid}.voices.json").write_text(RG.dumps(man))
        finally:
            con.close()
    except Exception as e:
        print("manifest failed:", e, flush=True)
    track = SB.write_track(STORE, vid, b.segments, b.blank) if (b.subs and b.blank) else None
    q = P.TIERS[P.tier(P.load())]["export"]   # Standard = លឿន, Premium = គុណភាពខ្ពស់
    if b.speed == "fast": q = _fast(q)
    q = _q(q, b.quality, src.name)
    layers, boxes = _layers(b)
    bgm = _bgm(b.bgm)
    W, H = G.probe(STORE, src.name)
    dur = G.duration(STORE, src.name) or 0.0
    args = SB.export_args(src.name, clips, track, out.name, q, bgm, layers, boxes, W, H, dur,
                          E.video_args(q["preset"], q["crf"]), audio_store=STORE)
    job = PR.run_job(STORE, args, vid, dur)
    job["url"] = f"/files/{out.name}"
    return {"job": True, "encoder": E.best()}


@app.get("/api/export_download")
def export_download(id: str):
    """Download completed MP4 with an attachment response for mobile Safari."""
    vid = pathlib.Path(id).name
    if len(vid) != 10 or any(ch not in "0123456789abcdef" for ch in vid):
        raise HTTPException(400, "ID Export មិនត្រឹមត្រូវ")
    out = STORE / f"{vid}_km.mp4"
    if not out.is_file():
        raise HTTPException(404, "មិនទាន់មាន video Export សម្រាប់គម្រោងនេះ")
    return FileResponse(
        out,
        media_type="application/octet-stream",
        filename=f"{vid}_km.mp4",
        headers={"Cache-Control": "no-store"},
    )


class TE(BaseModel): segments: list[dict]; kind: str = "mp3"; bgm: str = ""   # segments: {n,start,end,zh,km,char,audio}
@app.post("/api/tts_export")
def tts_export(b: TE):
    clips = [s for s in b.segments if s.get("audio")]
    if not clips: raise HTTPException(400, "មិនទាន់មានសំឡេង — ចុច Generate Khmer Audio ជាមុន")
    tag = uuid.uuid4().hex[:8]
    if b.kind == "zip":
        out = STORE / f"khmer_tts_{tag}.zip"; SB.build_zip(STORE, clips, out)
    else:
        out = STORE / f"khmer_voice_{tag}.mp3"; q = P.TIERS[P.tier(P.load())]["export"]
        guard(lambda: ff(*SB.audio_args(clips, out.name, q, _bgm(b.bgm), audio_store=STORE)))
    return {"url": f"/files/{out.name}"}

@app.post("/api/tts_import")
async def tts_import(files: list[UploadFile]):
    try: out = SB.import_audio(STORE, [(f.filename or "", await f.read()) for f in files])
    except zipfile.BadZipFile: raise HTTPException(400, "file ZIP មិនត្រឹមត្រូវ")
    if not out: raise HTTPException(400, "រកមិនឃើញ file សំឡេង (mp3 / wav / m4a / ogg / aac / flac)")
    return out

BGM_JOBS = {}
BGM_MAX_SECONDS = 118  # ទុកចន្លោះសុវត្ថិភាពមុនដែន ២ នាទីរបស់ UI


def _bgm_ff(timeout, *args):
    if timeout <= 0:
        raise subprocess.TimeoutExpired("ffmpeg", timeout)
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-nostats", "-loglevel", "error", *args],
        capture_output=True, text=True, cwd=STORE, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError("FFmpeg: " + (result.stderr or "")[-1000:])


def _bgm_channels(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
             "stream=channels", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=5,
        )
        return int(result.stdout.strip().splitlines()[0]) if result.returncode == 0 and result.stdout.strip() else 2
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return 2


def _demucs_command(model, wav, sep):
    return [sys.executable, "-m", "demucs", "-n", model, "--two-stems=vocals",
            "--shifts", "0", "--overlap", "0.1", "-o", str(sep), str(wav)]


def _quick_bgm_filter(channels):
    if channels > 1:
        # Center-cancel is near-instant for stereo mixes; centered vocals cancel out.
        return "pan=stereo|c0=0.5*FL-0.5*FR|c1=0.5*FR-0.5*FL"
    # Mono cannot be center-cancelled, so gently attenuate the main speech range instead.
    return "equalizer=f=1000:t=q:w=1.2:g=-8,equalizer=f=2500:t=q:w=1.2:g=-10"


def _bgm(n):
    """ទទួលឈ្មោះ ឬ URL → ឈ្មោះ file ក្នុង storage (ឬ None បើមិនមាន)"""
    n = pathlib.Path((n or "").split("?")[0]).name
    return n if n and (STORE / n).is_file() else None

@app.post("/api/bgm")
async def bgm_upload(id: str, file: UploadFile):
    import threading
    ext = pathlib.Path(file.filename or "").suffix.lower()
    vid = pathlib.Path(id).name
    data = await file.read()
    if ext in SB.AUD and (__import__("os").environ.get("KH_BGM_KEEP") == "1" or __import__("importlib.util").util.find_spec("demucs") is None):   # រក្សាទុកផ្ទាល់ តែពេលកំណត់ KH_BGM_KEEP=1
        name = f"{vid}_bgm{ext}"
        (STORE / name).write_bytes(data)
        kept = __import__("os").environ.get("KH_BGM_KEEP") == "1"
        if kept:
            return {"url": f"/files/{name}"}
        return {"url": f"/files/{name}", "vocals_removed": False,
                "warning": "Server នេះមិនដកសំដីទេ (គ្មាន Demucs)។ សូមដកសំដីលើ Mac មុន រួចទើប Upload"}
    if ext not in ({".mp4", ".mov", ".mkv", ".webm", ".avi", ".opus", ".wma"} | SB.AUD):
        raise HTTPException(400, "BGM ត្រូវជា mp3 / wav / m4a / ogg / aac / flac / mp4 / mov / mkv / webm")
    if BGM_JOBS.get(vid, {}).get("state") == "running":
        raise HTTPException(409, "កំពុងដំណើរការ BGM មុន សូមរង់ចាំ")
    BGM_JOBS[vid] = {"state": "running", "phase": "កំពុងរៀបចំសំឡេង…"}
    def job():
        started = time.monotonic()
        deadline = started + BGM_MAX_SECONDS
        tmp, wav, name = f"{vid}_bgm_src{ext}", f"{vid}_bgm_src.wav", f"{vid}_bgm.mp3"
        source, wav_path = STORE / tmp, STORE / wav
        sep = STORE / f"{vid}_sep"
        try:
            source.write_bytes(data)
            channels = _bgm_channels(source)
            BGM_JOBS[vid] = {"state": "running", "phase": "កំពុងបម្លែងសំឡេងសម្រាប់ដកសំដី…"}
            _bgm_ff(min(25, deadline - time.monotonic() - 5), "-i", tmp, "-vn", "-ac", "2", "-ar", "44100", wav)
            model = os.environ.get("KH_DEMUCS_MODEL", "htdemucs")
            demucs_error = ""
            BGM_JOBS[vid] = {"state": "running", "phase": "កំពុងដកសំដី (របៀបលឿន)…"}
            remaining = deadline - time.monotonic()
            demucs_timeout = min(90, remaining - 15)  # ទុកពេលសម្រាប់ fallback និង MP3 encode
            try:
                if demucs_timeout <= 0:
                    raise subprocess.TimeoutExpired("demucs", demucs_timeout)
                env = os.environ.copy()
                threads = max(1, min(4, os.cpu_count() or 2))
                env["OMP_NUM_THREADS"] = str(threads)
                env["MKL_NUM_THREADS"] = str(threads)
                subprocess.run(_demucs_command(model, wav_path, sep), check=True,
                               capture_output=True, text=True, timeout=demucs_timeout, env=env)
                separated = sep / model / f"{vid}_bgm_src" / "no_vocals.wav"
                if not separated.is_file():
                    raise RuntimeError("Demucs មិនបានបង្កើត no_vocals.wav")
                BGM_JOBS[vid] = {"state": "running", "phase": "កំពុងបង្កើតឯកសារ BGM…"}
                _bgm_ff(deadline - time.monotonic(), "-i", str(separated), "-c:a", "libmp3lame", "-b:a", "192k", name)
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, RuntimeError) as e:
                detail = getattr(e, "stderr", "") or str(e)
                if isinstance(detail, bytes):
                    detail = detail.decode("utf-8", "ignore")
                demucs_error = str(detail)[-350:]
                print("Demucs timed out/failed; using quick BGM filter:", demucs_error, flush=True)
                BGM_JOBS[vid] = {"state": "running", "phase": "កំពុងបញ្ចប់ដោយ filter លឿន…"}
                quick_filter = _quick_bgm_filter(channels)
                _bgm_ff(deadline - time.monotonic(), "-i", wav, "-af", quick_filter,
                        "-c:a", "libmp3lame", "-b:a", "192k", name)
                warning = ("Demucs យឺត ឬមិនដំណើរការ។ បានប្រើរបៀបលឿនជំនួស; សំឡេងអាចមិនស្អាតដូច Demucs។"
                           if channels > 1 else
                           "Demucs យឺត ឬមិនដំណើរការ។ BGM mono មិនអាចដកសំដីស្អាតដោយ filter លឿនបានទេ; បានបន្ថយសំឡេងក្នុងជួរភាសានិយាយ។")
            else:
                warning = ""
            if time.monotonic() - started > BGM_MAX_SECONDS:
                raise subprocess.TimeoutExpired("bgm job", BGM_MAX_SECONDS)
            BGM_JOBS[vid] = {"state": "done", "url": f"/files/{name}", "warning": warning,
                             "elapsed": round(time.monotonic() - started, 1)}
        except subprocess.TimeoutExpired:
            BGM_JOBS[vid] = {"state": "error", "error": "ការដកសំដីចំណាយជិត ២ នាទីហើយ។ សូមប្រើ BGM ខ្លីជាង ឬសាកម្ដងទៀត។"}
        except Exception as e:
            BGM_JOBS[vid] = {"state": "error", "error": str(e)[-500:]}
        finally:
            (STORE / tmp).unlink(missing_ok=True); wav_path.unlink(missing_ok=True)
            shutil.rmtree(sep, ignore_errors=True)
    threading.Thread(target=job, daemon=True).start()
    return {"job": True}

@app.get("/api/bgm_status")
def bgm_status(id: str):
    return BGM_JOBS.get(pathlib.Path(id).name, {"state": "none"})

@app.middleware("http")
async def _fresh_ui(request, call_next):
    """ការពារ UI ចាស់៖ `index.html` មិន cache · asset មាន hash → cache បានយូរ

    បើគ្មាន header នេះ Electron/Chromium អាចបង្ហាញ UI ចាស់ក្រោយ update
    (ហេតុអ្វី progress bar ចាស់នៅតែលេចឡើងទោះបានដំឡើងកំណែថ្មីរួច)។
    """
    resp = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith(".html"):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
    elif path.startswith("/assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


app.mount("/files", StaticFiles(directory=STORE), name="files")
# ព្រមាននៅ console បើ UI build ចាស់ជាងកូដ (រត់ពី source)
try:
    from .appinfo import ui_info as _ui_info
    if _ui_info().get("stale"):
        print("⚠ frontend/dist ចាស់ជាង frontend/src — UI ថ្មីមិនទាន់បង្ហាញ។ "
              "Rebuild: cd frontend && npm install && npm run build", flush=True)
except Exception:
    pass

DIST = ROOT / "frontend" / "dist"

# index.html បញ្ជូនតាម backend (មិនមែន StaticFiles) ដើម្បី៖
#   ១. បញ្ចូលបដា "UI ចាស់" ទោះ bundle ខ្លួនឯងជាកំណែចាស់ (ដំណើរការពី source)
#   ២. no-store ជានិច្ច → Electron/browser មិនបង្ហាញ UI ចាស់ក្រោយ update
if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/")
def index_page():
    idx = DIST / "index.html"
    if not idx.exists():
        raise HTTPException(
            404, "UI មិនទាន់ build — សូមរត់: cd frontend && npm install && npm run build "
                 "(ឬ bash scripts/ui_build.sh)")
    html = idx.read_text(encoding="utf-8", errors="ignore")
    ui = {}
    try:
        from .appinfo import ui_info
        ui = ui_info()
    except Exception:
        ui = {}
    if ui.get("stale"):
        badge = (
            '<script>window.addEventListener("load",function(){if(document.getElementById("kh-uistale"))return;'
            'var b=document.createElement("a");b.id="kh-uistale";b.href="#";'
            'b.textContent="⚠ UI ចាស់ — សូម rebuild (cd frontend && npm run build)";'
            'b.title="frontend/dist ចាស់ជាង frontend/src · rebuild: bash scripts/ui_build.sh";'
            'b.onclick=function(e){e.preventDefault();location.reload();};'
            'b.style.cssText="position:fixed;left:50%;transform:translateX(-50%);bottom:34px;z-index:99999;"'
            '+";background:#f43f5e;color:#fff;font:700 12px sans-serif;padding:6px 14px;border-radius:999px;"'
            '+";text-decoration:none;box-shadow:0 6px 20px #f43f5e66";document.body.appendChild(b);});</script>'
        )
        html = html.replace("</body>", badge + "</body>")
    return HTMLResponse(html, headers={
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    })


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")

from .overlay import register as _reg_overlay; _reg_overlay(app, STORE, ff, guard)

from .layers import register as _reg_layers; _reg_layers(app, STORE, ff, guard)

from .blur import register as _reg_blur; _reg_blur(app, STORE, ff, guard)

from .finish import register as _reg_finish; _reg_finish(app, STORE, ff, guard)

from .progress import register as _reg_prog; _reg_prog(app, STORE, guard)
from .appinfo import register as _reg_info; _reg_info(app)
from .updates import register as _reg_upd; _reg_upd(app)
