"""Export ជា background job + progress ពិតពី FFmpeg (`-progress pipe:1`)

API៖
  POST /api/export        → {"job": true}  (ចាប់ផ្តើម) ឬ {"url": ...} បើឥតធ្វើអ្វី
  GET  /api/export_status → {state: running|done|error, percent, eta, speed, url, error}
  GET  /api/encoder       → {encoder, hardware, label}   (បង្ហាញក្នុង UI)
"""
import pathlib
import re
import subprocess
import threading
import time
from fastapi import APIRouter, HTTPException

from . import encode as E

JOBS = {}
_T = re.compile(r"^(\w+)=(.*)$")


def _ffmpeg_bin():
    return "ffmpeg"


def run_job(store, args, key, dur):
    """រត់ ffmpeg ក្នុង thread ហើយធ្វើបច្ចុប្បន្នភាព JOBS[key] ជាបន្តបន្ទាប់"""
    job = JOBS.setdefault(key, {})
    job.update({"state": "running", "percent": 0.0, "eta": 0.0, "speed": 0.0, "url": "", "error": "", "started": time.time()})

    def watch():
        t0 = time.time()
        try:
            p = subprocess.Popen([_ffmpeg_bin(), "-y", "-hide_banner", "-nostats", "-loglevel", "error",
                                  "-progress", "pipe:1", *args],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=store, bufsize=1)
            err_tail = []
            for line in p.stdout:
                m = _T.match(line.strip())
                if not m:
                    continue
                k, v = m.group(1), m.group(2)
                if k == "out_time":
                    try:
                        hh, mm, ss = v.split(":")
                        done = int(hh) * 3600 + int(mm) * 60 + float(ss)
                    except ValueError:
                        continue
                    if dur and dur > 0:
                        pct = max(0.0, min(99.9, done / dur * 100.0))
                        el = time.time() - t0
                        job["percent"] = round(pct, 1)
                        job["eta"] = round(max(0.0, el / max(pct, 0.5) * (100.0 - pct)), 1) if pct > 0.5 else 0.0
                        job["speed"] = round(done / el, 2) if el > 0 else 0.0
                elif k == "progress" and v == "end":
                    job["percent"] = 100.0
            rest = p.stderr.read() or ""
            p.wait()
            if p.returncode != 0:
                job.update({"state": "error", "error": ("FFmpeg: " + rest[-1200:]).strip() or "FFmpeg បរាជ័យ"})
            else:
                job.update({"state": "done", "percent": 100.0, "eta": 0.0,
                            "elapsed": round(time.time() - t0, 1)})
        except Exception as e:
            job.update({"state": "error", "error": str(e)[-800:]})

    threading.Thread(target=watch, daemon=True).start()
    return job


def register(app, STORE, guard):
    r = APIRouter()

    @r.get("/api/export_status")
    def status(id: str):
        j = JOBS.get(pathlib.Path(id).name)
        if not j:
            return {"state": "none"}
        out = {k: j.get(k) for k in ("state", "percent", "eta", "speed", "url", "error", "elapsed")}
        if j.get("state") == "running" and j.get("url"):
            out["url"] = j["url"]
        return out

    @r.get("/api/encoder")
    def encoder():
        return E.info()

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
