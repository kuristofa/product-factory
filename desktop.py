"""Native desktop window for the AI Product Production Factory.

Runs the Flask app quietly in a background thread and shows it in a real OS window
(via pywebview / WebView2 on Windows) — no browser, no URL. Double-click start_ui.bat,
or run `python desktop.py`.
"""
from __future__ import annotations

import socket
import sys
import threading
import time

from app import app


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _serve(port: int) -> None:
    # use_reloader=False is required: the reloader would fork and break threading.
    app.run(host="127.0.0.1", port=port, threaded=True, use_reloader=False)


def _wait_ready(port: int, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _browser(url: str) -> int:
    import webbrowser
    webbrowser.open(url)
    print(f"  Opening in your browser instead: {url}")
    print("  Leave this window open while you use the app. Press Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    return 0


def main() -> int:
    port = _free_port()
    threading.Thread(target=_serve, args=(port,), daemon=True).start()
    if not _wait_ready(port):
        print("The app server didn't start in time. Try `python app.py` to diagnose.")
        return 1
    url = f"http://127.0.0.1:{port}"

    try:
        import webview
    except ImportError:
        print("\npywebview isn't installed. Install it with:")
        print("    pip install -r requirements.txt")
        return _browser(url)

    try:
        webview.create_window(
            "AI-powered Product Production Factory", url,
            width=920, height=780, min_size=(720, 620),
        )
        webview.start()
        return 0
    except Exception as e:  # noqa: BLE001
        import traceback
        print("\nCouldn't open the native window. Full error:")
        traceback.print_exc()
        if sys.platform.startswith("win"):
            print("\n  If that mentions WebView2 or Edge, install the free "
                  "'Microsoft Edge WebView2 Runtime' from Microsoft, then try again.")
        return _browser(url)


if __name__ == "__main__":
    sys.exit(main())
