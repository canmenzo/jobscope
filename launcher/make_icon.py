"""Render launcher/jobscope.ico — the taskbar icon for the Job Scope shortcut.

A scope reticle (the "scope" in jobscope) with a green lock-on dot for the
match it found. Drawn at 1024px and downsampled with LANCZOS so the 16px
taskbar rendering stays crisp.

    python launcher/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024
OUT = Path(__file__).resolve().parent / "jobscope.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

BG_TOP, BG_BOTTOM = (28, 34, 48), (15, 17, 21)
BLUE = (59, 130, 246, 255)
GREEN = (52, 211, 153, 255)


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius, fill=255)
    return m


def gradient(size, top, bottom):
    g = Image.new("RGB", (1, size))
    px = g.load()
    for y in range(size):
        t = y / (size - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return g.resize((size, size))


def main():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(gradient(S, BG_TOP, BG_BOTTOM), (0, 0), rounded_mask(S, int(S * 0.22)))
    d = ImageDraw.Draw(img)

    c = S / 2
    ring_r = S * 0.30
    ring_w = int(S * 0.075)
    d.ellipse([c - ring_r, c - ring_r, c + ring_r, c + ring_r], outline=BLUE, width=ring_w)

    # Reticle ticks: four spokes crossing the ring, leaving a gap at the centre.
    tick_w = int(S * 0.062)
    inner, outer = S * 0.12, S * 0.44
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d.line([c + dx * inner, c + dy * inner, c + dx * outer, c + dy * outer],
               fill=BLUE, width=tick_w)

    # Lock-on: the match the scope found.
    hx, hy, hr = c + S * 0.135, c - S * 0.135, S * 0.085
    d.ellipse([hx - hr * 1.85, hy - hr * 1.85, hx + hr * 1.85, hy + hr * 1.85],
              fill=(15, 17, 21, 255))
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=GREEN)

    frames = [img.resize(s, Image.LANCZOS) for s in SIZES]
    frames[-1].save(OUT, format="ICO", sizes=SIZES, append_images=frames[:-1])
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
