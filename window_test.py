"""Standalone pywebview test — isolates the window from the app entirely.

Run:  python window_test.py
If a window appears saying "It works.", pywebview/WebView2 are fine and the problem is
in how the app launches it. If it fails, the full error below tells us exactly why.
"""
import sys
import traceback

print("Python:", sys.version.split()[0])

try:
    import webview
    print("pywebview version:", getattr(webview, "__version__", "unknown"))
except Exception:
    print("Could not import pywebview:")
    traceback.print_exc()
    sys.exit(1)

try:
    import clr  # noqa: F401  (pythonnet — the Windows WebView2 backend uses it)
    print("pythonnet (clr): available")
except Exception as e:  # noqa: BLE001
    print("pythonnet (clr): NOT available ->", e)

print("\nCreating a test window...")
try:
    webview.create_window(
        "WebView Test",
        html=("<body style='font-family:sans-serif;padding:40px'>"
              "<h1>It works.</h1><p>Close this window to finish the test.</p></body>"),
        width=520, height=320,
    )
    print("Starting — a window should appear now. Close it when you're done.")
    webview.start()
    print("\nwebview.start() returned normally — the window opened and was closed. All good.")
except Exception:
    print("\n*** WEBVIEW FAILED — full error below (copy all of this) ***\n")
    traceback.print_exc()
