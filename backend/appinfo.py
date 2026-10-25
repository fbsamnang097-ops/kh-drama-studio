"""GET /api/version → កំណែពី file VERSION (ប្រភពតែមួយ) + ស្ថានភាព UI build"""
import re
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

def ui_info():
    """UI (frontend/dist) ស្រស់ឬអត់?

    ហេតុអ្វីសំខាន់៖ `frontend/dist` មិនចូល git (gitignored) → ពេលរត់ពី source
    ការ `git pull` មិនធ្វើបច្ចុប្បន្នភាព UI ទេ។ ដូច្នេះ backend ត្រូវដឹង និងរាយការណ៍។
    ក្នុង app ដែល build រួច (PyInstaller) គ្មាន `frontend/src` → stale = False។
    """
    dist = ROOT / "frontend" / "dist"
    idx = dist / "index.html"
    if not idx.exists():
        return {"built": False, "stale": False, "bundle": None, "built_at": None}
    bundle, built_at = None, None
    try:
        html = idx.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"assets/(index-[A-Za-z0-9_-]+\.js)", html)
        bundle = m.group(1) if m else None
        built_at = int(idx.stat().st_mtime)
    except OSError:
        pass
    src, stale = ROOT / "frontend" / "src", False
    if src.exists() and built_at:
        try:
            newest = max(p.stat().st_mtime for p in src.rglob("*") if p.is_file())
            stale = newest > built_at + 1     # កូដថ្មីជាង build → ត្រូវ rebuild
        except (OSError, ValueError):
            stale = False
    return {"built": bool(bundle), "stale": stale, "bundle": bundle, "built_at": built_at}


def register(app):
    r = APIRouter()

    @r.get("/api/version")
    def version(): return {"version": _version(), "ui": ui_info()}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new: rt.remove(x)
    rt[0:0] = new   # ដាក់មុន static mount
