import subprocess, uuid, pathlib, zipfile, sys, shutil
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import providers as P
from . import subs as SB
from . import graph as G
from . import cast as C
from . import diarize as D
from . import identity as ID
from . import voices as V
from . import encode as E
from . import progress as PR

from .paths import ROOT, STORE   # exe: STORE ក្នុង folder អ្នកប្រើ

app = FastAPI(title="KH Drama Studio AI")

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
        scan = C.scan([s.get("zh", "") for s in segs])   # តួអង្គស្វ័យប្រវត្តិ
        for s, it in zip(segs, scan["items"]):
            s["char"] = it["char"]; s["conf"] = it["conf"]
        return segs
    return guard(run)

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
            "limitations": [
                "edge-tts (ឥតគិតថ្លៃ) មានសំឡេងខ្មែរតែ ២ (Piseth ប្រុស · Sreymom ស្រី) — ចាស់/ក្មេង/តួប្រុស ២ នាក់ បង្កើតដោយ rate · pitch · volume",
                "បើកំណត់ Azure/Google/ElevenLabs ក្នុង Settings នឹងប្រើសំឡេងពិតរបស់ពួកគេ",
            ]}
    if id:
        data["cast"] = ID.load_cast(STORE, id)
    return data


class DetectIn(BaseModel):
    id: str
    segments: list[dict] = []      # [{start,end,zh}]
    use_audio: bool = True
    voicebook: bool = True


@app.post("/api/characters/detect")
def characters_detect(b: DetectIn):
    """វិភាគតួអង្គពី សំឡេង + អត្ថបទ (diarization) — តួអង្គថេរពេញរឿង"""
    def run():
        segs = [s for s in b.segments if isinstance(s, dict)]
        audio = None
        video = STORE / f"{b.id}.mp4"
        if b.use_audio and video.exists() and segs:
            try:
                audio = D.analyze_segments(video, segs)
            except Exception as e:
                print("diarization failed:", e, flush=True)
                audio = None
        prev = ID.load_cast(STORE, b.id) or {}
        book = ID.load_voicebook(STORE) if b.voicebook else {}
        res = ID.resolve(segs, audio, video_id=b.id, voicebook=book,
                         previous=prev.get("characters"))
        # ការជ្រើសដោយដៃរបស់អ្នកប្រើ ឈ្នះស្វ័យប្រវត្តិ
        ID.apply_overrides(res, (prev or {}).get("overrides") or {})
        if b.voicebook:
            ID.bind_voicebook(STORE, res["characters"])
        ID.save_cast(STORE, b.id, {**res, "overrides": (prev or {}).get("overrides") or {}})
        return res
    return guard(run)


class AssignIn(BaseModel):
    id: str
    overrides: dict = {}           # {char_id: voice_id}
    reset: bool = False


@app.post("/api/characters/assign")
def characters_assign(b: AssignIn):
    """ជ្រើសសំឡេងដោយដៃ → រក្សាទុកជារៀងរហូត (រហូតដល់ reset)"""
    def run():
        data = ID.load_cast(STORE, b.id) or {"characters": [], "items": []}
        ov = {} if b.reset else {**(data.get("overrides") or {}), **b.overrides}
        (data.setdefault("characters", []))
        for c in data["characters"]:
            if b.reset:
                c["manual"] = False
            v = ov.get(c["id"])
            if v and v in V.VOICES:
                c["voice"], c["manual"], c["source"] = v, True, "manual"
        data["overrides"] = ov
        ID.save_cast(STORE, b.id, data)
        # ភ្ជាប់ឈ្មោះ → សំឡេង សម្រាប់ភាគក្រោយ
        book = ID.load_voicebook(STORE)
        for c in data["characters"]:
            if c.get("manual") and c.get("name") and c.get("named", True):
                book[c["name"]] = c["voice"]
        ID.save_voicebook(STORE, book)
        return {"ok": True, "characters": data["characters"], "overrides": ov}
    return guard(run)


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
    char_id: str = ""       # character id (ត្រូវការ video)
    video: str = ""         # video id (សម្រាប់រក cast)
    gender: str = "male"    # តម្លៃចាស់ (backward compat)
    speed: float = 0.0


def _voice_for(b):
    """char_id → voice ពី cast ដែលរក្សាទុក · បើគ្មាន → char/voice id"""
    if b.video and b.char_id:
        data = ID.load_cast(STORE, b.video) or {}
        for c in data.get("characters", []):
            if c.get("id") == b.char_id:
                return c.get("voice") or c.get("role") or b.char or b.gender
    return b.char or b.gender


@app.post("/api/tts")
def tts(b: Sp):
    def run():
        name = f"{uuid.uuid4().hex[:10]}.mp3"
        voice = _voice_for(b)
        (STORE / name).write_bytes(P.tts(b.text, voice, b.speed, P.load()))
        return {"url": f"/files/{name}", "char": P.voice_profile(voice)[1], "voice": voice}
    return guard(run)

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
    track = SB.write_track(STORE, vid, b.segments, b.blank) if (b.subs and b.blank) else None
    q = P.TIERS[P.tier(P.load())]["export"]   # Standard = លឿន, Premium = គុណភាពខ្ពស់
    if b.speed == "fast": q = _fast(q)
    q = _q(q, b.quality, src.name)
    layers, boxes = _layers(b)
    bgm = _bgm(b.bgm)
    W, H = G.probe(STORE, src.name)
    dur = G.duration(STORE, src.name) or 0.0
    args = SB.export_args(src.name, clips, track, out.name, q, bgm, layers, boxes, W, H, dur, E.video_args(q["preset"], q["crf"]))
    job = PR.run_job(STORE, args, vid, dur)
    job["url"] = f"/files/{out.name}"
    return {"job": True, "encoder": E.best()}

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
        guard(lambda: ff(*SB.audio_args(clips, out.name, q, _bgm(b.bgm))))
    return {"url": f"/files/{out.name}"}

@app.post("/api/tts_import")
async def tts_import(files: list[UploadFile]):
    try: out = SB.import_audio(STORE, [(f.filename or "", await f.read()) for f in files])
    except zipfile.BadZipFile: raise HTTPException(400, "file ZIP មិនត្រឹមត្រូវ")
    if not out: raise HTTPException(400, "រកមិនឃើញ file សំឡេង (mp3 / wav / m4a / ogg / aac / flac)")
    return out

BGM_JOBS = {}

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
    BGM_JOBS[vid] = {"state": "running"}
    def job():
        tmp, wav, name = f"{vid}_bgm_src{ext}", f"{vid}_bgm_src.wav", f"{vid}_bgm.mp3"
        sep = STORE / f"{vid}_sep"
        try:
            (STORE / tmp).write_bytes(data)
            ff("-i", tmp, "-vn", "-ac", "2", "-ar", "44100", wav)
            import os as _os
            model = _os.environ.get("KH_DEMUCS_MODEL", "htdemucs")
            try:   # ដកសំដីដោយ Demucs (មិន fallback ទៅវិធីមិនស្អាតទៀតទេ)
                subprocess.run([sys.executable, "-m", "demucs", "-n", model, "--two-stems=vocals", "-o", str(sep), str(STORE / wav)],
                               check=True, capture_output=True)
                ff("-i", str(sep / model / f"{vid}_bgm_src" / "no_vocals.wav"), "-c:a", "libmp3lame", "-b:a", "192k", name)
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                err = (e.stderr.decode("utf-8", "ignore") if getattr(e, "stderr", None) else str(e))[-400:]
                print("Demucs failed:", err, flush=True)
                raise RuntimeError("ដកសំដីចេញមិនបាន (Demucs): " + err)
            BGM_JOBS[vid] = {"state": "done", "url": f"/files/{name}"}
        except Exception as e:
            BGM_JOBS[vid] = {"state": "error", "error": str(e)[-500:]}
        finally:
            (STORE / tmp).unlink(missing_ok=True); (STORE / wav).unlink(missing_ok=True)
            shutil.rmtree(sep, ignore_errors=True)
    threading.Thread(target=job, daemon=True).start()
    return {"job": True}

@app.get("/api/bgm_status")
def bgm_status(id: str):
    return BGM_JOBS.get(pathlib.Path(id).name, {"state": "none"})

app.mount("/files", StaticFiles(directory=STORE), name="files")
if (ROOT / "frontend/dist").exists():
    app.mount("/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="web")

from .overlay import register as _reg_overlay; _reg_overlay(app, STORE, ff, guard)

from .layers import register as _reg_layers; _reg_layers(app, STORE, ff, guard)

from .blur import register as _reg_blur; _reg_blur(app, STORE, ff, guard)

from .finish import register as _reg_finish; _reg_finish(app, STORE, ff, guard)

from .progress import register as _reg_prog; _reg_prog(app, STORE, guard)
from .appinfo import register as _reg_info; _reg_info(app)
