"""Launcher សម្រាប់ exe/app: ត្រៀម ffmpeg ក្នុង bundle, បើក server, បើក browser"""
import os, sys, socket, threading, webbrowser, pathlib, subprocess, multiprocessing

# SSL: certificates for downloads (Demucs model, TTS, APIs) inside the packaged app
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except Exception:
    pass

FROZEN = bool(getattr(sys, "frozen", False))

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

def prep_path():
    b = pathlib.Path(getattr(sys, "_MEIPASS", pathlib.Path(__file__).parent)) / "bin"
    if b.is_dir():
        for f in b.iterdir():
            try: os.chmod(f, 0o755)
            except OSError: pass
        os.environ["PATH"] = str(b) + os.pathsep + os.environ.get("PATH", "")

def free_port(start=8000):
    for p in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0: return p
    return start

def main():
    multiprocessing.freeze_support()
    prep_path()
    if FROZEN and sys.argv[1:3] == ["-m", "demucs"]:
        sys.argv = ["demucs"] + sys.argv[3:]
        from demucs.separate import main as _demucs_main
        _demucs_main(); return
    from backend.main import app
    if "--check" in sys.argv:
        for t in ("ffmpeg", "ffprobe"):
            subprocess.run([t, "-version"], check=True, capture_output=True)
        print("CHECK_OK"); return
    import uvicorn
    _p = sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv[:-1] else None
    port = int(_p) if _p else free_port(); url = f"http://127.0.0.1:{port}"
    print(f"KH Drama Studio -> {url}")
    print("បិទបង្អួចនេះដើម្បីបញ្ចប់ / Close this window to quit")
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    main()
