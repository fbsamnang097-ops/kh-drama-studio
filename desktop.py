import socket
import threading
import time

import uvicorn
import webview

from backend.main import app

PORT = 8000


def serve():
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


def wait_for_port(port: int, timeout: float = 60) -> None:
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError("Server did not start")


if __name__ == "__main__":
    threading.Thread(target=serve, daemon=True).start()
    wait_for_port(PORT)
    webview.create_window("KH Drama Studio", f"http://127.0.0.1:{PORT}", width=1280, height=820)
    webview.start()