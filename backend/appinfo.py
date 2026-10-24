"""GET /api/version → កំណែពី file VERSION (ប្រភពតែមួយ)"""
from fastapi import APIRouter
from .paths import ROOT

def _vfile():
    import sys, pathlib
    for d in (getattr(sys, "_MEIPASS", None), pathlib.Path(sys.executable).parent, ROOT):
        if d and (pathlib.Path(d) / "VERSION").exists():
            return pathlib.Path(d) / "VERSION"
    return ROOT / "VERSION"

def _version():
    try: return _vfile().read_text(encoding="utf-8").strip() or "dev"
    except OSError: return "dev"

def register(app):
    r = APIRouter()

    @r.get("/api/version")
    def version(): return {"version": _version()}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
