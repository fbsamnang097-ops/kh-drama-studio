"""Layers (logo / sponsor / overlay / text): upload + apply លើវីដេអូដែល Export រួច

ការគូរ layer ត្រូវបានធ្វើក្នុង `graph.py` (pass តែមួយ)។ បើអ្នកចង់បាន Logo, Sponsor,
Overlay, Khmer Text និង Blur ក្នុងពេលតែមួយ → ប្រើ `/api/export` ឬ `/api/finish`។
"""
import pathlib
from fastapi import APIRouter, UploadFile, HTTPException

from . import graph as G
from .finish import apply_fx

EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
VID = {".mp4"}   # វីដេអូ: អនុញ្ញាតតែ logo / sponsor
KINDS = G.LAYER_ORDER   # ["logo", "sponsor", "overlay", "text"] — លំដាប់ដាក់ (ក្រោយ = លើគេ)


def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/layer")
    async def layer_upload(id: str, kind: str, file: UploadFile):
        if kind not in KINDS: raise HTTPException(400, "kind មិនត្រឹមត្រូវ")
        ext = ".png" if kind == "text" else pathlib.Path(file.filename or "").suffix.lower()
        if ext not in EXT and not (ext in VID and kind in ("logo", "sponsor")):
            raise HTTPException(400, "ត្រូវជា PNG / JPG / JPEG / WebP / GIF (Logo និង Sponsor ទទួល MP4 ផងដែរ)")
        vid = pathlib.Path(id).name
        for old in STORE.glob(f"{vid}_ly_{kind}.*"): old.unlink(missing_ok=True)
        name = f"{vid}_ly_{kind}{ext}"
        with open(STORE / name, "wb") as out:   # សរសេរម្តង 1MB មិនផ្ទុកទាំង file ក្នុង RAM
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        return {"url": f"/files/{name}"}

    @r.post("/api/layers_apply")
    def layers_apply(b: dict):
        out = apply_fx(STORE, ff, guard, b.get("id", ""), b.get("layers") or [],
                       b.get("boxes") or [], out_suffix="_km_ly.mp4")
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
