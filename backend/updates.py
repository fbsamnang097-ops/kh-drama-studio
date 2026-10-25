"""ជូនដំណឹងកំណែថ្មី (update check) — ពិនិត្យ GitHub Releases

ហេតុអ្វីត្រូវការ៖ អ្នកប្រើដំឡើង app រួចហើយមិនដឹងថាមានកំណែថ្មី។
ម៉ូឌុលនេះពិនិត្យ release ចុងក្រោយ រួចប្រាប់ UI ឱ្យបង្ហាញបដា
「🎁 មានកំណែថ្មី vX — ទាញយក」 ជាមួយតំណទាញយកផ្ទាល់។

លក្ខណៈ៖
  • គ្មាន token (repo សាធារណៈ) · គ្មាន dependency ថ្មី (urllib)
  • cache ៣០ នាទី → មិនហៅ GitHub ញឹកញាប់
  • គ្មាន internet → ok:false (មិន crash) និងរក្សាលទ្ធផលចាស់បើមាន
  • KH_UPDATE_OFFLINE=1 → បិទការពិនិត្យ (តេស្ត/ក្រៅបណ្តាញ)
  • KH_UPDATE_URL / KH_UPDATE_REPO → សម្រាប់តេស្ត ឬ mirror
"""

import json
import os
import re
import time
import urllib.request

from fastapi import APIRouter

from .appinfo import _version

REPO = os.environ.get("KH_UPDATE_REPO", "fbsamnang097-ops/kh-drama-studio")
API = "https://api.github.com/repos/{repo}/releases/latest"
TTL = 30 * 60                      # វិនាទី — cache លទ្ធផល
_CACHE = {"ts": 0.0, "data": None}


def _vtuple(v):
    """'v1.0.23' → (1, 0, 23) · មិនត្រឹមត្រូវ → (0,)"""
    nums = re.findall(r"\d+", str(v or "")[:16])
    return tuple(int(x) for x in nums[:4]) or (0,)


def newer(latest, current):
    """latest ថ្មីជាង current? (ប្រៀបធៀបតាមលេខ មិនមែន string)"""
    a, b = _vtuple(latest), _vtuple(current)
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def _pick(assets, *needles):
    """រក asset តាមឈ្មោះ (ឧ. 'arm64.dmg') → url"""
    for a in assets or []:
        name = (a.get("name") or "").lower()
        if all(n.lower() in name for n in needles):
            return a.get("browser_download_url") or a.get("url") or ""
    return ""


def _payload(release, current, cached=False):
    tag = (release.get("tag_name") or release.get("name") or "").strip()
    latest = tag.lstrip("vV")
    assets = release.get("assets") or []
    downloads = {
        "mac_arm": _pick(assets, "arm64", ".dmg") or _pick(assets, "aarch64", ".dmg"),
        "mac_intel": _pick(assets, "x64", ".dmg") or _pick(assets, "intel", ".dmg"),
        "windows": _pick(assets, ".exe") or _pick(assets, "setup", ".exe"),
    }
    page = release.get("html_url") or f"https://github.com/{REPO}/releases/latest"
    return {
        "ok": True,
        "current": current,
        "latest": latest,
        "tag": tag,
        "available": bool(latest) and newer(latest, current),
        "url": page,
        "notes": (release.get("body") or "")[:6000],
        "published": release.get("published_at") or "",
        "title": release.get("name") or tag,
        "downloads": downloads,
        "assets": [{"name": a.get("name"), "size": a.get("size"),
                    "url": a.get("browser_download_url")} for a in assets][:12],
        "checked_at": int(time.time()),
        "cached": cached,
    }


def _error(msg, current, stale=None):
    out = {"ok": False, "available": False, "current": current,
           "latest": (stale or {}).get("latest", ""),
           "tag": (stale or {}).get("tag", ""),
           "url": f"https://github.com/{REPO}/releases/latest",
           "error": str(msg)[:240], "checked_at": int(time.time()), "cached": False}
    if stale:                       # រក្សាព័ត៌មានចាស់ (internet ដាច់មួយភ្លែត)
        out.update({k: stale.get(k) for k in ("latest", "tag", "url", "downloads",
                                              "notes", "published", "title")})
        out["available"] = stale.get("available", False)
        out["stale"] = True
    return out


def check(force=False, timeout=6.0):
    """→ dict សម្រាប់ UI (មិនបោះ exception)"""
    current = _version()
    now = time.time()
    if not force and _CACHE["data"] and now - _CACHE["ts"] < TTL:
        return {**_CACHE["data"], "cached": True}

    if os.environ.get("KH_UPDATE_OFFLINE") == "1":
        return _error("បិទការពិនិត្យកំណែ (KH_UPDATE_OFFLINE=1)", current, _CACHE["data"])

    url = os.environ.get("KH_UPDATE_URL") or API
    url = url.format(repo=REPO)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "KHDramaStudio/" + current,
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            release = json.loads(r.read().decode("utf-8", "ignore") or "{}")
        data = _payload(release, current)
        _CACHE["ts"], _CACHE["data"] = time.time(), data
        return data
    except Exception as e:          # គ្មាន internet · rate-limit · repo ឯកជន
        return _error(f"{type(e).__name__}: {e}", current, _CACHE["data"])


def register(app):
    r = APIRouter()

    @r.get("/api/update")
    def update(refresh: bool = False):
        """កំណែចុងក្រោយ + តំណទាញយក (សម្រាប់បដាជូនដំណឹងក្នុង app)"""
        return check(force=refresh)

    @r.get("/api/update/current")
    def current():
        return {"version": _version(), "repo": REPO,
                "releases": f"https://github.com/{REPO}/releases"}

    before = list(app.router.routes)
    app.include_router(r)
    rt = app.router.routes
    new = [x for x in rt if x not in before]
    for x in new:
        rt.remove(x)
    rt[0:0] = new                   # ដាក់មុន static mount
