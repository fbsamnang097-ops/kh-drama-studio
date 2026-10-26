#!/usr/bin/env python3
"""Verify the frontend bundle copied into each electron-builder app payload."""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "release").resolve()
version = pathlib.Path("VERSION").read_text(encoding="utf-8").strip()
required = ("/api/segments/fix", "/api/characters/detect", version)
found = []
for index in root.rglob("index.html"):
    parts = index.as_posix().split("/")
    if "frontend" not in parts or "dist" not in parts:
        continue
    # Only inspect the backend resources copied into the actual Electron app payload.
    if "resources" not in parts or "backend" not in parts:
        continue
    html = index.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"assets/(index-[A-Za-z0-9_-]+\.js)", html)
    if not match:
        raise SystemExit(f"No frontend JS bundle referenced by {index}")
    bundle_path = index.parent / "assets" / match.group(1)
    if not bundle_path.is_file():
        raise SystemExit(f"Missing copied UI bundle: {bundle_path}")
    bundle = bundle_path.read_text(encoding="utf-8", errors="replace")
    missing = [marker for marker in required if marker not in bundle]
    if missing:
        raise SystemExit(f"Stale/incomplete UI in installer payload {index}: {missing}")
    found.append((index, match.group(1)))

if not found:
    raise SystemExit(f"No embedded frontend/dist payload found under {root}")
for index, bundle in found:
    print(f"INSTALLER_UI_OK version={version} bundle={bundle} payload={index}")
