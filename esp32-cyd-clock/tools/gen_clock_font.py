#!/usr/bin/env python3
"""Generate a lightweight GFXfont (Adafruit_GFX bitmap font format)
containing ONLY '0'-'9' and ':' (0x30-0x3A, a contiguous range),
rasterized from a real bold condensed TTF at a point size tuned so
"14:25" lands in the target box (260-300w x 100-130h). No freetype/
fontconvert C toolchain needed -- PIL does the rasterization.

Usage: python3 tools/gen_clock_font.py
Regenerates ClockDigits.h in the project root.
"""
import argparse
import os
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Bold.ttf"
CHARS = "0123456789:"  # 0x30-0x3A, contiguous -- required by GFXfont's single first/last range
TEST_STRING = "14:25"
# Round 3 (TFT_eSPI migration, "slightly larger" request): current
# TFT_eSPI built-in Font 8 measured 249x75 on real hardware -- width is
# already inside the new 240-255 target, only height needs to grow
# (75 -> 85-95). No explicit px_size constraint this round (unlike
# round 2) -- search the full range and pick the tallest that fits.
TARGET_W = (240, 255)
TARGET_H = (85, 95)
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "ClockDigits.h")
STRUCT_NAME = "ClockDigits"


def tight_glyph_bbox(font, ch, px_size, baseline_xy):
    """Renders ch at a known baseline position (anchor='ls' -- left,
    baseline) and scans for the tight ink bounding box. Returns
    (minx, miny, maxx, maxy) in the same coordinate space as
    baseline_xy, or None for a blank glyph."""
    canvas = px_size * 3
    img = Image.new("L", (canvas, canvas), 0)
    draw = ImageDraw.Draw(img)
    bx, by = baseline_xy
    draw.text((bx, by), ch, font=font, fill=255, anchor="ls")
    arr = img.load()
    minx = miny = maxx = maxy = None
    for yy in range(img.height):
        for xx in range(img.width):
            if arr[xx, yy] > 90:
                if minx is None or xx < minx: minx = xx
                if maxx is None or xx > maxx: maxx = xx
                if miny is None or yy < miny: miny = yy
                if maxy is None or yy > maxy: maxy = yy
    if minx is None:
        return None
    return minx, miny, maxx, maxy


def measure(px_size):
    """Tight custom advance (glyph width + small fixed gap) instead of
    the font's own (more generous) advance metric -- narrows the
    string enough to let a taller point size still fit the width
    ceiling. Baseline is anchored at a fixed point so yOffset comes out
    correctly signed (negative = above baseline, standard GFXfont
    convention)."""
    font = ImageFont.truetype(FONT_PATH, px_size)
    gap = max(2, px_size // 24)
    baseline = (px_size, px_size * 2)  # arbitrary fixed anchor, only relative deltas matter
    total_w = 0
    max_h = 0
    for ch in TEST_STRING:
        bbox = tight_glyph_bbox(font, ch, px_size, baseline)
        if bbox is None:
            continue
        minx, miny, maxx, maxy = bbox
        total_w += (maxx - minx + 1) + gap
        max_h = max(max_h, maxy - miny + 1)
    total_w -= gap
    return total_w, max_h


def find_best_size():
    # Round 3: no explicit px_size constraint given -- maximize height
    # within the WxH target box (same approach as round 1).
    best = None
    for px in range(40, 220):
        w, h = measure(px)
        fits = TARGET_W[0] <= w <= TARGET_W[1] and TARGET_H[0] <= h <= TARGET_H[1]
        if fits and (best is None or h > best[1]):
            best = (px, h, w)
    return best


def generate(px_size, out_path, struct_name):
    font = ImageFont.truetype(FONT_PATH, px_size)
    gap = max(2, px_size // 24)
    baseline = (px_size, px_size * 2)
    glyphs = []
    bitmap_bytes = bytearray()

    for ch in CHARS:
        bbox = tight_glyph_bbox(font, ch, px_size, baseline)
        if bbox is None:
            glyphs.append({"ch": ch, "bitmapOffset": len(bitmap_bytes), "width": 0, "height": 0,
                            "xAdvance": px_size // 2, "xOffset": 0, "yOffset": 0})
            continue
        minx, miny, maxx, maxy = bbox
        gw = maxx - minx + 1
        gh = maxy - miny + 1
        # GFXfont convention: xOffset/yOffset are the glyph's top-left
        # corner position RELATIVE TO THE CURSOR (which sits on the
        # baseline) -- yOffset negative for glyphs above the baseline.
        xOffset = minx - baseline[0]
        yOffset = miny - baseline[1]
        advance = gw + gap  # tight custom advance, not the font's own (more generous) metric

        img = Image.new("L", (px_size * 3, px_size * 3), 0)
        draw = ImageDraw.Draw(img)
        draw.text(baseline, ch, font=font, fill=255, anchor="ls")
        arr = img.load()
        bit_buf = 0
        bit_count = 0
        glyph_bytes = bytearray()
        for yy in range(miny, maxy + 1):
            for xx in range(minx, maxx + 1):
                bit = 1 if arr[xx, yy] > 90 else 0
                bit_buf = (bit_buf << 1) | bit
                bit_count += 1
                if bit_count == 8:
                    glyph_bytes.append(bit_buf)
                    bit_buf = 0
                    bit_count = 0
        if bit_count > 0:
            bit_buf <<= (8 - bit_count)
            glyph_bytes.append(bit_buf)

        glyphs.append({
            "ch": ch, "bitmapOffset": len(bitmap_bytes), "width": gw, "height": gh,
            "xAdvance": round(advance), "xOffset": xOffset, "yOffset": yOffset,
        })
        bitmap_bytes.extend(glyph_bytes)

    ascent, descent = font.getmetrics()
    y_advance = ascent + descent

    with open(out_path, "w") as f:
        f.write("// Auto-generated lightweight numeric font (0-9, ':' only) for esp32-cyd-clock.\n")
        f.write(f"// Source: {os.path.basename(FONT_PATH)} at {px_size}px, generated by tools/gen_clock_font.py.\n")
        f.write(f"// Adafruit_GFX-compatible GFXfont format -- usable with tft.setFont(&{struct_name}).\n")
        f.write("#pragma once\n#include <Adafruit_GFX.h>\n\n")
        f.write(f"const uint8_t {struct_name}Bitmaps[] PROGMEM = {{\n  ")
        for i, b in enumerate(bitmap_bytes):
            f.write(f"0x{b:02X}, ")
            if (i + 1) % 12 == 0:
                f.write("\n  ")
        f.write("\n};\n\n")
        f.write(f"const GFXglyph {struct_name}Glyphs[] PROGMEM = {{\n")
        for g in glyphs:
            f.write(f"  {{ {g['bitmapOffset']}, {g['width']}, {g['height']}, {g['xAdvance']}, {g['xOffset']}, {g['yOffset']} }}, // '{g['ch']}'\n")
        f.write("};\n\n")
        f.write(f"const GFXfont {struct_name} PROGMEM = {{\n")
        f.write(f"  (uint8_t *){struct_name}Bitmaps, (GFXglyph *){struct_name}Glyphs, 0x30, 0x3A, {y_advance}\n")
        f.write("};\n")

    return {"px_size": px_size, "bitmap_bytes": len(bitmap_bytes), "glyph_count": len(glyphs), "y_advance": y_advance}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default=FONT_PATH, help="source TTF path")
    ap.add_argument("--out", default=OUT_PATH, help="output .h path")
    ap.add_argument("--struct-name", default=STRUCT_NAME, help="GFXfont struct name")
    args = ap.parse_args()
    FONT_PATH = args.font
    OUT_PATH = args.out
    STRUCT_NAME = args.struct_name

    best = find_best_size()
    if not best:
        print("No size found that fits target box", file=sys.stderr)
        sys.exit(1)
    px, h, w = best
    print(f"Selected px_size={px} -> measured {w}x{h} for \"{TEST_STRING}\" ({os.path.basename(FONT_PATH)})")
    stats = generate(px, OUT_PATH, STRUCT_NAME)
    print(stats)
