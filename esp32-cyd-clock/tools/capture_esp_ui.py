#!/usr/bin/env python3
"""Capture a real screenshot + UI-state snapshot directly from the
esp32-cyd-clock firmware's debug HTTP server (/debug/screenshot,
/debug/ui-state). This is the ACTUAL rendering pipeline's output -- not
a simulator, not a mock -- see screenshot.h/.cpp for how the firmware
mirrors every real draw call into the returned image.

Usage:
    python3 tools/capture_esp_ui.py --host 192.168.1.136
    python3 tools/capture_esp_ui.py --host 192.168.1.136 --qa   # deterministic QA state first

Writes to test-results/esp-ui-capture/:
    latest.png, latest.json          (always overwritten)
    capture-NNN.png, capture-NNN.json (incrementing, kept as history)
"""
import argparse
import json
import os
import sys
import time
import urllib.request

try:
    from PIL import Image
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "test-results", "esp-ui-capture")


def fetch(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def next_capture_index(out_dir):
    n = 1
    while os.path.exists(os.path.join(out_dir, f"capture-{n:03d}.png")):
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="ESP32 IP address (from Serial log's [WIFI] Connected line)")
    ap.add_argument("--qa", action="store_true", help="switch the firmware to deterministic QA state before capturing")
    ap.add_argument("--out", default=None, help="output directory (default: reports/esp-ui-capture next to the workspace, or ./test-results/esp-ui-capture)")
    args = ap.parse_args()

    out_dir = args.out or os.path.abspath(OUT_DIR)
    os.makedirs(out_dir, exist_ok=True)

    base = f"http://{args.host}"

    if args.qa:
        req = urllib.request.Request(f"{base}/debug/show-screen?mode=qa", method="POST")
        urllib.request.urlopen(req, timeout=10).read()
        # Give the firmware's loop() a few iterations to actually perform
        # the one-time QA redraw (clock/header/weather) before reading the
        # shadow framebuffer -- without this, a screenshot taken
        # immediately after the mode switch can catch a partially-drawn
        # frame (e.g. the weather band cleared+redrawn while an earlier
        # "Weather offline" string was mid-draw), which looks like
        # garbled/doubled text. Real bug found this way, not assumed.
        time.sleep(1.5)
        print("[capture] Switched firmware to QA deterministic state")

    ui_state_raw = fetch(f"{base}/debug/ui-state")
    ui_state = json.loads(ui_state_raw)
    print("[capture] ui-state:", json.dumps(ui_state, indent=2))

    bmp_bytes = fetch(f"{base}/debug/screenshot", timeout=30)
    print(f"[capture] screenshot: {len(bmp_bytes)} bytes (BMP)")

    idx = next_capture_index(out_dir)
    bmp_path = os.path.join(out_dir, f"capture-{idx:03d}.bmp")
    json_path = os.path.join(out_dir, f"capture-{idx:03d}.json")
    with open(bmp_path, "wb") as f:
        f.write(bmp_bytes)
    with open(json_path, "w") as f:
        json.dump(ui_state, f, indent=2)

    png_path_latest = os.path.join(out_dir, "latest.png")
    json_path_latest = os.path.join(out_dir, "latest.json")
    png_path_numbered = os.path.join(out_dir, f"capture-{idx:03d}.png")

    if HAVE_PIL:
        img = Image.open(bmp_path)
        img.save(png_path_latest)
        img.save(png_path_numbered)
        print(f"[capture] Converted BMP -> PNG: {png_path_latest}")
    else:
        print("[capture] PIL not available -- keeping .bmp only (rename latest.bmp manually if needed)", file=sys.stderr)
        import shutil
        shutil.copy(bmp_path, os.path.join(out_dir, "latest.bmp"))

    with open(json_path_latest, "w") as f:
        json.dump(ui_state, f, indent=2)

    print(f"[capture] Saved capture-{idx:03d} and latest.* in {out_dir}")


if __name__ == "__main__":
    main()
