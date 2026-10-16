#!/usr/bin/env python3
"""Stage 4: render one caption PNG per beat (white heavy text on a dark rounded pill).

Backends, in order of preference:
  1. macOS: scripts/caption.swift via swiftc (CoreText, handles Urdu/Arabic/Hindi shaping and bidi)
  2. Pillow (pip install pillow): fine for Latin-script captions; complex scripts may not shape correctly
ffmpeg's drawtext/subtitles filters are not used because many ffmpeg builds lack libfreetype/libass.

  python3 scripts/captions.py <project> [--ids 2]
Caption text = beat "caption" if set, else "narration".
"""
import os
import shutil
import subprocess
import sys

import project as P

a = P.args("Render caption PNGs")
doc = P.load(a.project)
W = 1080 if doc.get("aspect", "9:16") in ("9:16", "3:4", "4:5") else 1920
HERE = os.path.dirname(os.path.abspath(__file__))


def swift_renderer():
    if sys.platform != "darwin" or not shutil.which("swiftc"):
        return None
    cache = os.path.join(os.path.expanduser("~"), ".cache", "vox-director-fal")
    os.makedirs(cache, exist_ok=True)
    binary = os.path.join(cache, "caption")
    src = os.path.join(HERE, "caption.swift")
    if not os.path.exists(binary) or os.path.getmtime(binary) < os.path.getmtime(src):
        print("compiling caption renderer (one-time, ~30s)...")
        subprocess.run(["swiftc", "-O", "-o", binary, src], check=True, capture_output=True)
    return lambda out, text: subprocess.run([binary, out, str(W), text], check=True, capture_output=True)


def pillow_renderer():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    def font(size):
        for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
            if os.path.exists(f):
                return ImageFont.truetype(f, size)
        return ImageFont.load_default()

    def render(out, text):
        size = int(W * 0.058)
        fnt, pad = font(size), int(W * 0.06)
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        words, lines, cur = text.split(), [], ""
        for w in words:  # greedy wrap to the inner width
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=fnt) <= W - 2 * pad - size:
                cur = t
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        lh = int(size * 1.3)
        H = lh * len(lines) + 2 * pad
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        tw = max(d.textlength(l, font=fnt) for l in lines)
        px, py = size * 0.55, size * 0.3
        d.rounded_rectangle([(W - tw) / 2 - px, pad - py, (W + tw) / 2 + px, H - pad + py],
                            radius=int(size * 0.45), fill=(13, 13, 13, 158))
        for i, l in enumerate(lines):
            d.text((W / 2, pad + i * lh + lh / 2), l, font=fnt, anchor="mm", fill="white",
                   stroke_width=2, stroke_fill="black")
        img.save(out)

    return render


render = swift_renderer() or pillow_renderer()
if not render:
    sys.exit("No caption renderer: on macOS install Xcode command line tools (xcode-select --install); "
             "elsewhere `pip install pillow`. Or set \"captions\": false in beats.json.")
for b in P.selected(doc, a.ids):
    text = b.get("caption") or b.get("narration")
    if text:
        render(os.path.join(a.project, "captions", f"cap{b['id']}.png"), text)
        print(f"cap{b['id']}.png")
