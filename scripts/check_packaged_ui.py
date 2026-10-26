#!/usr/bin/env python3
"""Smoke-check packaged app version, required UI features, and iOS PWA assets."""
import json
import pathlib
import re
import sys
import urllib.request

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8731"
EXPECTED_VERSION = pathlib.Path("VERSION").read_text(encoding="utf-8").strip()


def get(url):
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.read()


info = json.loads(get(BASE + "/api/version"))
assert info.get("version") == EXPECTED_VERSION, (
    f"backend version mismatch: expected {EXPECTED_VERSION}, got {info.get('version')}"
)
ui = info.get("ui") or {}
assert ui.get("built") and not ui.get("stale"), f"UI build invalid: {ui}"
html = get(BASE + "/").decode("utf-8", "replace")
match = re.search(r"/assets/(index-[A-Za-z0-9_-]+\.js)", html)
assert match, "served index.html has no Vite bundle reference"
bundle = get(BASE + match.group(0)).decode("utf-8", "replace")
required = ("/api/segments/fix", "/api/characters/detect", "Add to Home Screen", EXPECTED_VERSION)
missing = [marker for marker in required if marker not in bundle]
assert not missing, f"served frontend bundle is missing current version/features: {missing}"
assert ui.get("bundle") == match.group(1), (
    f"bundle mismatch: /api/version reports {ui.get('bundle')}, index.html serves {match.group(1)}"
)
assert 'rel="manifest" href="/manifest.json"' in html, "PWA manifest link is missing"
assert 'apple-mobile-web-app-capable' in html, "iOS standalone metadata is missing"
manifest = json.loads(get(BASE + "/manifest.json"))
assert manifest.get("display") == "standalone", f"PWA display must be standalone: {manifest.get('display')}"
for asset in ("/icon-192.png", "/icon-512.png", "/apple-touch-icon.png", "/sw.js"):
    get(BASE + asset)
print(f"PACKAGED_UI_OK version={EXPECTED_VERSION} bundle={match.group(1)} features={len(required)} pwa_assets=4")
