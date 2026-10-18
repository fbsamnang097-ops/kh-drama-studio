import subprocess, uuid, pathlib, zipfile, sys, shutil
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from . import providers as P
from . import subs as SB

ROOT = pathlib.Path(__file__).parent.parent
STORE = ROOT / "storage"; STORE.mkdir(exist_ok=True)
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
    mp3 = STORE / f"{b.id}.mp3"
    def run():
        ff("-i", str(STORE / f"{b.id}.mp4"), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(mp3))
        return P.stt(mp3, P.load())
    return guard(run)

class Tr(BaseModel): lines: list[str]
@app.post("/api/translate")
def translate(b: Tr): return guard(lambda: P.translate(b.lines, P.load()))

class Sp(BaseModel): text: str; gender: str = "male"; speed: float = 0.0
@app.post("/api/tts")
def tts(b: Sp):
    def run():
        name = f"{uuid.uuid4().hex[:10]}.mp3"
        (STORE / name).write_bytes(P.tts(b.text, b.gender, b.speed, P.load()))
        return {"url": f"/files/{name}"}
    return guard(run)

class Ex(BaseModel): id: str; segments: list[dict]; subs: bool = True; blank: str = ""; bgm: str = ""   # segments: {start,end,km,audio,png}
@app.post("/api/export")
def export(b: Ex):
    src, out, srt = STORE / f"{b.id}.mp4", STORE / f"{b.id}_km.mp4", STORE / f"{b.id}.srt"
    t = lambda s: f"{int(s//3600):02}:{int(s%3600//60):02}:{int(s%60):02},{int(s*1000)%1000:03}"
    srt.write_text("\n".join(f"{i+1}\n{t(s['start'])} --> {t(s['end'])}\n{s['km']}\n" for i, s in enumerate(b.segments)), encoding="utf-8")
    clips = [s for s in b.segments if s.get("audio")]
    if not clips: raise HTTPException(400, "សូមចុច Generate Khmer Audio ជាមុន")
    track = SB.write_track(STORE, b.id, b.segments, b.blank) if (b.subs and b.blank) else None
    q = P.TIERS[P.tier(P.load())]["export"]   # Standard = លឿន, Premium = គុណភាពខ្ពស់
    guard(lambda: ff(*SB.export_args(src.name, clips, track, out.name, q, _bgm(b.bgm))))
    return {"url": f"/files/{out.name}"}

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
        return {"url": f"/files/{name}"}
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
