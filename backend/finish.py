"""Apply Layers + Blur ក្នុង pass តែមួយ លើវីដេអូដែល Export រួច

`POST /api/finish` {id, layers:[...], boxes:[...]} → `{id}_km_fx.mp4`
ប្រើពេលអ្នកបាន Export រួចហើយ ចង់បន្ថែម/កែ Logo, Sponsor, Overlay, Khmer Text ឬ Blur
ដោយមិនចាំបាច់ Export សំឡេង/អក្សរឡើងវិញ។ បើចង់បានទាំងអស់ក្នុងពេលតែមួយ → ប្រើ
`/api/export` (ដែលបញ្ចូល layer + blur ដែរ)។

Route ចាស់ (`/api/layers_apply`, `/api/overlay_apply`, `/api/blur_apply`) នៅដំណើរការដូចដើម
ដោយហៅ helper តែមួយនេះ → លទ្ធផលដូចគ្នា និងមិន encode ច្រើនជាន់។
"""
import pathlib
from fastapi import APIRouter, HTTPException

from . import graph as G


def base_video(STORE, vid):
    """វីដេអូដែល Export រួច (ជ្រើសឯកសារចុងក្រោយដែលមាន)"""
    for suffix in ("_km.mp4", "_km_fx.mp4", "_km_ly.mp4", "_km_bl.mp4", "_km_ov.mp4"):
        p = STORE / f"{vid}{suffix}"
        if p.is_file():
            return p
    return None


def apply_fx(STORE, ff, guard, vid, layers, boxes, out_suffix="_km_fx.mp4", src=None):
    """ដាក់ layer + blur លើវីដេអូ Export រួច → ឈ្មោះ file លទ្ធផល"""
    vid = pathlib.Path(str(vid)).name
    src = src or base_video(STORE, vid)
    if src is None:
        raise HTTPException(400, "សូម Export វីដេអូជាមុន")
    G.prepare(STORE, vid, layers)
    items = G.layer_inputs(STORE, layers)
    boxes = [bx for bx in (boxes or []) if isinstance(bx, dict)]
    if not items and not boxes:
        raise HTTPException(400, "គ្មាន Layer ឬ Blur ដែលបានបើក")
    if len(items) > 8:
        raise HTTPException(400, "ដាក់បានតែ 8 layer ក្នុងមួយដង")
    out = f"{vid}{out_suffix}"
    guard(lambda: G.finish(STORE, src.name, out, items, boxes, ff))
    return out


def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/finish")
    def finish_route(b: dict):
        out = apply_fx(STORE, ff, guard, b.get("id", ""), b.get("layers") or [], b.get("boxes") or [])
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
