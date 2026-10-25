"""តេស្តប្រព័ន្ធជូនដំណឹងកំណែថ្មី (backend/updates.py · /api/update)

រត់:  python tests/test_updates.py
  T1  ប្រៀបធៀបកំណែ (semver) ត្រឹមត្រូវ
  T2  ជ្រើស asset តាម OS (arm64/x64 .dmg · .exe)
  T3  release ថ្មីជាង → available:true + តំណទាញយក
  T4  កំណែស្មើគ្នា → available:false
  T5  offline → ok:false មិន crash
  T6  /api/update (server ពិត) + cache
  T7  /api/update/current
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"   [{detail}]" if detail else ""))


# ---------------- fake GitHub ----------------
class FakeRelease(BaseHTTPRequestHandler):
    payload = {}
    fail = False

    def do_GET(self):                                    # noqa: N802
        if FakeRelease.fail:                             # ត្រាប់ GitHub បិទ / គ្មាន internet
            self.send_response(503)
            self.end_headers()
            return
        body = json.dumps(self.payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):                           # ស្ងាត់
        pass


def release_json(tag, repo="fbsamnang097-ops/kh-drama-studio"):
    base = f"https://github.com/{repo}/releases/download/{tag}"
    names = [f"KH-Drama-Studio-{tag}-arm64.dmg", f"KH-Drama-Studio-{tag}-x64.dmg",
             f"KH-Drama-Studio-{tag}.exe", "latest.yml"]
    return {
        "tag_name": tag,
        "name": f"{tag} — Release",
        "html_url": f"https://github.com/{repo}/releases/tag/{tag}",
        "published_at": "2026-10-25T07:08:57Z",
        "body": "## អ្វីថ្មី\n- កែកំហុស\n- បន្ថែមមុខងារ",
        "assets": [{"name": n, "size": 123456, "browser_download_url": f"{base}/{n}"} for n in names],
    }


def main():
    from backend import updates as U

    print("\n=== T1: semver comparison ===")
    cases = [("1.0.23", "1.0.22", True), ("1.0.22", "1.0.22", False),
             ("v1.0.23", "1.0.22", True), ("1.0.9", "1.0.10", False),
             ("1.1.0", "1.0.99", True), ("2.0.0", "1.99.99", True),
             ("1.0.22", "1.0.23", False), ("", "1.0.0", False)]
    bad = [(l, c, e) for l, c, e in cases if U.newer(l, c) != e]
    check("T1: version comparison is numeric, not string", not bad, str(bad))

    print("\n=== T2: OS download links ===")
    rel = release_json("v1.0.99")
    pay = U._payload(rel, "1.0.22")
    d = pay["downloads"]
    check("T2: arm64 dmg detected", d["mac_arm"].endswith("arm64.dmg"), d["mac_arm"].rsplit("/", 1)[-1])
    check("T2: intel dmg detected", d["mac_intel"].endswith("x64.dmg"), d["mac_intel"].rsplit("/", 1)[-1])
    check("T2: windows exe detected", d["windows"].endswith(".exe"), d["windows"].rsplit("/", 1)[-1])

    print("\n=== T3: newer release → available ===")
    check("T3: available true", pay["available"] is True, f"{pay['current']} → {pay['latest']}")
    check("T3: notes + release page included", bool(pay["notes"]) and pay["url"].startswith("https://github.com/"))

    print("\n=== T4: same version → not available ===")
    same = U._payload(release_json("v1.0.22"), "1.0.22")
    check("T4: available false when equal", same["available"] is False, same["latest"])

    print("\n=== T5: offline does not crash ===")
    os.environ["KH_UPDATE_OFFLINE"] = "1"
    U._CACHE["data"] = None
    off = U.check(force=True)
    check("T5: ok false + error message", off["ok"] is False and bool(off.get("error")), off.get("error"))
    check("T5: still returns current version + download page",
          bool(off["current"]) and "releases" in off["url"], off["url"].rsplit("/", 2)[-2:])
    del os.environ["KH_UPDATE_OFFLINE"]

    print("\n=== T6: real /api/update endpoint (fake GitHub server) ===")
    srv = HTTPServer(("127.0.0.1", 0), FakeRelease)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    FakeRelease.payload = release_json("v1.0.99")

    tmp = tempfile.mkdtemp(prefix="khupd_")
    os.environ["KH_DATA_DIR"] = tmp
    os.environ["KH_UPDATE_URL"] = f"http://127.0.0.1:{port}/releases/latest"
    os.environ["KH_TTS_STUB"] = "1"
    env = {**os.environ, "PATH": os.path.dirname(sys.executable) + ":" + os.environ.get("PATH", ""),
           "PYTHONPATH": ROOT}
    api_port = int(os.environ.get("KH_TEST_PORT", "8771"))
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app",
                             "--host", "127.0.0.1", "--port", str(api_port)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{api_port}"
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(base + "/api/version", timeout=1)
                break
            except Exception:
                time.sleep(0.25)

        def get(path):
            with urllib.request.urlopen(base + path, timeout=20) as r:
                return json.load(r), r.status

        j, code = get("/api/update?refresh=1")
        check("T6: endpoint returns 200", code == 200, str(code))
        check("T6: sees the newer release", j.get("available") is True and j.get("latest") == "1.0.99",
              f"{j.get('current')} → {j.get('latest')}")
        check("T6: download buttons present for all OSes",
              all(j.get("downloads", {}).get(k) for k in ("mac_arm", "mac_intel", "windows")))
        j2, _ = get("/api/update")
        check("T6: cached on the 2nd call (no extra GitHub hit)", j2.get("cached") is True, str(j2.get("cached")))

        cur, _ = get("/api/update/current")
        check("T7: /api/update/current returns version + releases page",
              bool(cur.get("version")) and cur.get("releases", "").startswith("https://github.com/"), str(cur))

        print("\n=== T7b: no internet / bad URL → graceful ===")
        FakeRelease.fail = True                          # server subprocess មិនឃើញ env ថ្មី → ធ្វើឱ្យ fake បរាជ័យ
        bad, code = get("/api/update?refresh=1")
        check("T7b: provider error → ok:false, no crash", code == 200 and bad.get("ok") is False, bad.get("error"))
        check("T7b: user still gets a download page link", "github.com" in (bad.get("url") or ""), bad.get("url"))
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        srv.shutdown()

    print(f"\n{'=' * 56}\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", ", ".join(FAIL))
        return 1
    print("ALL UPDATE-NOTICE TESTS PASSED ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
