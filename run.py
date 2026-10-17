"""ដំណើរការ: python run.py  → build frontend (ម្តងដំបូង), បើក Server, បើក Browser ស្វ័យប្រវត្តិ"""
import subprocess, threading, webbrowser, pathlib, shutil, sys
import uvicorn
ROOT = pathlib.Path(__file__).parent
FE = ROOT / "frontend"
PORT = 8000
if not (FE / "dist").exists():
    npm = shutil.which("npm")
    if not npm: sys.exit("សូមដំឡើង Node.js ជាមុន: https://nodejs.org")
    subprocess.check_call([npm, "install"], cwd=FE)
    subprocess.check_call([npm, "run", "build"], cwd=FE)
threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()  # Auto-open
uvicorn.run("backend.main:app", host="127.0.0.1", port=PORT)
