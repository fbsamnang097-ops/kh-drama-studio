"""Blur boxes (ថេរ ឬដើរតាម keyframe) លើវីដេអូដែល Export រួច

ការគូរត្រូវបានធ្វើក្នុង `graph.py` (pass តែមួយ ជាមួយ layer) — ដូច្នេះ Blur និង Logo /
Sponsor / Overlay / Khmer Text ចេញមកជាវីដេអូតែមួយ ដោយមិន encode ច្រើនជាន់។
"""
from fastapi import APIRouter

from .finish import apply_fx


def register(app, STORE, ff, guard):
    r = APIRouter()

    @r.post("/api/blur_apply")
    def blur_apply(b: dict):
        out = apply_fx(STORE, ff, guard, b.get("id", ""), b.get("layers") or [],
                       b.get("boxes") or [], out_suffix="_km_bl.mp4")
        return {"url": f"/files/{out}"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
