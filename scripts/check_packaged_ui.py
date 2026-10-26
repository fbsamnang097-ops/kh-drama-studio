#!/usr/bin/env python3
"""Smoke-check that a packaged backend serves the current version and UI bundle."""
import json
import pathlib
import re
import sys
import urllib.error
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
required = ("/api/segments/fix", "/api/characters/detect")
missing = [marker for marker in required if marker not in bundle]
assert not missing, f"served frontend bundle is missing required current features: {missing}"
assert ui.get("bundle") == match.group(1), (
    f"bundle mismatch: /api/version reports {ui.get('bundle')}, index.html serves {match.group(1)}"
)
print(f"PACKAGED_UI_OK version={EXPECTED_VERSION} bundle={match.group(1)} required={len(required)}")
