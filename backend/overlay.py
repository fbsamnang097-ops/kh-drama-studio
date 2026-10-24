"""Custom Overlay (PNG/JPG/WebP/GIF): upload + apply លើវីដេអូដែល Export រួច

ការគូរត្រូវបានធ្វើក្នុង `graph.py` (pass តែមួយ) — ដូច Logo / Sponsor / Khmer Text / Blur។
"""
import pathlib
from fastapi import APIRouter, UploadFile, HTTPException

from . import graph as G
from .finish import apply_fx

EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/overlay")
    async def overlay_upload(id: str, file: UploadFile):
        ext = pathlib.Path(file.filename or "").suffix.lower()
        if ext not in EXT: raise HTTPException(400, "Overlay ត្រូវជា PNG / JPG / JPEG / WebP / GIF")
        vid = pathlib.Path(id).name
        for old in STORE.glob(f"{vid}_ov.*"): old.unlink(missing_ok=True)
        name = f"{vid}_ov{ext}"
        (STORE / name).write_bytes(await file.read())
        return {"url": f"/files/{name}"}

    @r.post("/api/overlay_apply")
    def overlay_apply(b: dict):
        o = b.get("overlay") or {}
        name = pathlib.Path(str(o.get("file") or "").split("?")[0]).name
        if not o.get("enabled") or not name or not (STORE / name).is_file():
            raise HTTPException(400, "Overlay ត្រូវបានបិទ ឬមិនទាន់មាន file")
        layer = {"kind": "overlay", "enabled": True, "file": name,
                 "x": o.get("x", 50), "y": o.get("y", 85),
                 "size": o.get("size", 25), "opacity": o.get("opacity", 90)}
        out = apply_fx(STORE, ff, guard, b.get("id", ""), [layer], [], out_suffix="_km_ov.mp4")
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]   # តែ route ថ្មីរបស់ overlay
    for x in new: rt.remove(x)
    rt[0:0] = new                              # ដាក់មុន static mount
