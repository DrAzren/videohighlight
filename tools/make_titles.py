"""Render the film's typography + light-leak layer as a transparent PNG sequence.

Usage: python3 make_titles.py EDL.json FONT_DIR OUT_DIR

Reads "text" and "leaks" from the edit list. Each text block has t0/t1, an optional
readability scrim ("bottom" | "center" | "closing"), optional gold hairline "rules"
and a lower-third "bar", and a list of lines:
  {"text", "font", "weight", "size", "y", "x" (left-aligned if given), "color",
   "track" (letter spacing, em), "anim": fade | rise | track | wipe, "delay"}
Frames with nothing on them are hard links to one blank PNG.
"""
import json
import math
import os
import sys
from functools import lru_cache
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

edl = json.loads(Path(sys.argv[1]).read_text())
FONTS, OUT = Path(sys.argv[2]), Path(sys.argv[3])
W, H = edl["size"]
FPS = edl["fps"]
NF = int(round(edl["duration"] * FPS))
FADE = 0.45

PALETTE = {
    "ivory": (247, 241, 228),
    "champagne": (226, 201, 150),
    "gold": None,                      # gradient fill
}
GOLD_STOPS = [(0.0, (250, 236, 196)), (0.45, (222, 188, 116)), (0.75, (190, 146, 74)), (1.0, (236, 210, 150))]
NAVY = (8, 14, 28)


def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


@lru_cache(maxsize=None)
def font(name, weight, size):
    f = ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
    try:
        f.set_variation_by_axes([weight])
    except OSError:
        pass
    return f


@lru_cache(maxsize=64)
def gold_fill(w, h):
    y = np.linspace(0, 1, h)
    pos = [p for p, _ in GOLD_STOPS]
    col = np.stack([np.interp(y, pos, [c[k] for _, c in GOLD_STOPS]) for k in range(3)], 1)
    rgb = np.repeat(col[:, None, :], w, 1).astype(np.uint8)
    return Image.fromarray(rgb, "RGB")


def text_mask(line, track):
    """Greyscale mask of a line with letter spacing `track` (em). Returns (mask, ascent-offset)."""
    f = font(line["font"], line.get("weight", 400), line["size"])
    s = line["text"]
    sp = track * line["size"]
    widths = [f.getlength(c) for c in s]
    total = sum(widths) + sp * (len(s) - 1)
    asc, desc = f.getmetrics()
    pad = int(line["size"] * 0.5)
    img = Image.new("L", (int(total) + 2 * pad, asc + desc + 2 * pad), 0)
    d = ImageDraw.Draw(img)
    x = pad
    if sp == 0:
        d.text((x, pad), s, font=f, fill=255)
    else:
        for c, w in zip(s, widths):
            d.text((x, pad), c, font=f, fill=255)
            x += w + sp
    return img, pad, asc


@lru_cache(maxsize=512)
def rendered_line(key, track_q):
    line = json.loads(key)
    mask, pad, asc = text_mask(line, track_q / 1000)
    w, h = mask.size
    color = line.get("color", "ivory")
    if color == "gold":
        fill = gold_fill(w, h)
    else:
        fill = Image.new("RGB", (w, h), PALETTE[color])
    rgba = fill.convert("RGBA")
    rgba.putalpha(mask)
    # soft drop shadow + faint glow for legibility on busy footage
    sh = mask.filter(ImageFilter.GaussianBlur(line["size"] * 0.12))
    shadow = Image.new("RGBA", (w, h), NAVY + (0,))
    shadow.putalpha(sh.point(lambda v: min(255, int(v * 1.1))))
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(shadow, (0, int(line["size"] * 0.03)))
    if color == "gold":
        gl = mask.filter(ImageFilter.GaussianBlur(line["size"] * 0.25))
        glow = Image.new("RGBA", (w, h), (255, 214, 140, 0))
        glow.putalpha(gl.point(lambda v: int(v * 0.28)))
        out.alpha_composite(glow)
    out.alpha_composite(rgba)
    return out, pad, asc


def fit_size(line):
    """Shrink lines that would leave the 82 % safe width."""
    line = dict(line)
    while True:
        f = font(line["font"], line.get("weight", 400), line["size"])
        w = f.getlength(line["text"]) + line.get("track", 0) * line["size"] * (len(line["text"]) - 1)
        if w <= W * 0.82 or line["size"] < 30:
            return line
        line["size"] = int(line["size"] * 0.95)


@lru_cache(maxsize=8)
def scrim(kind):
    y = np.linspace(0, 1, H)[:, None]
    if kind == "bottom":
        a = np.clip((y - 0.44) / 0.22, 0, 1) ** 1.2 * 0.88
    elif kind == "closing":
        a = np.clip((y - 0.42) / 0.36, 0, 1) ** 1.3 * 0.86
    else:                                # center band behind titles
        a = 0.32 + np.exp(-((y - 0.45) / 0.09) ** 2) * 0.58
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., :3] = NAVY
    arr[..., 3] = (a * 255).astype(np.uint8)
    return arr


def leak(t):
    """Warm anamorphic light leak; returns float alpha map at 1/8 res and colour, or None."""
    for lk in edl.get("leaks", []):
        p = (t - lk["at"]) / lk["dur"]
        if 0 <= p <= 1:
            k = math.sin(math.pi * p) ** 1.5 * lk["peak"]
            w, h = W // 8, H // 8
            yy, xx = np.mgrid[0:h, 0:w]
            cx = (lk["x"] + (p - 0.5) * 0.5 * (1 if lk["x"] < 0.5 else -1)) * w
            blob = np.exp(-(((xx - cx) / (w * 0.55)) ** 2 + ((yy - h * 0.45) / (h * 0.5)) ** 2))
            streak = np.exp(-((yy - h * (0.35 + 0.2 * p)) / (h * 0.04)) ** 2) * 0.5
            return np.clip((blob + streak) * k, 0, 1)
    return None


def frame(i):
    t = i / FPS
    dst = OUT / f"{i:05d}.png"
    active = [b for b in edl["text"] if b["t0"] - 0.01 <= t <= b["t1"] + 0.01]
    lk = leak(t)
    if not active and lk is None:
        os.link(OUT / "blank.png", dst)
        return
    base = np.zeros((H, W, 4), np.float32)
    canvas = None
    for b in active:
        a_in = smooth((t - b["t0"]) / FADE)
        a_out = smooth((b["t1"] - t) / FADE)
        blk = min(a_in, a_out)
        if b.get("scrim"):
            s = scrim(b["scrim"]).astype(np.float32)
            sa = s[..., 3:4] / 255 * blk
            base[..., :3] = base[..., :3] * (1 - sa) + s[..., :3] * sa
            base[..., 3:4] = base[..., 3:4] + sa * (1 - base[..., 3:4])
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGBA")
    if lk is not None:
        col = np.zeros((H // 8, W // 8, 4), np.uint8)
        col[..., 0], col[..., 1], col[..., 2] = 255, 196, 128
        col[..., 3] = (lk * 255).astype(np.uint8)
        img.alpha_composite(Image.fromarray(col, "RGBA").resize((W, H), Image.BILINEAR))
    d = ImageDraw.Draw(img)
    for b in active:
        a_out = smooth((b["t1"] - t) / FADE)
        for ry in b.get("rules", []):                   # gold hairlines growing from centre
            p = smooth((t - b["t0"] - 0.1) / 1.1) * a_out
            if p > 0:
                half = W * 0.17 * p
                y = int(ry * H)
                d.rectangle([W / 2 - half, y, W / 2 + half, y + 3], fill=(214, 178, 108, int(220 * p)))
        if "bar" in b:                                  # lower-third accent bar wiping in
            bar = b["bar"]
            p = smooth((t - b["t0"] - bar.get("delay", 0)) / 0.6) * a_out
            if p > 0:
                x0, y = bar["x"] * W, int(bar["y"] * H)
                d.rectangle([x0, y, x0 + bar["w"] * W * p, y + 5], fill=(214, 178, 108, int(235 * a_out)))
        for line in b["lines"]:
            line = fit_size(line)
            lt = t - b["t0"] - line.get("delay", 0)
            a = smooth(lt / FADE) * a_out
            if a <= 0:
                continue
            anim = line.get("anim", "fade")
            track = line.get("track", 0.0)
            dy = 0
            if anim == "track":                         # letters settle inwards while fading up
                track += 0.12 * (1 - smooth(lt / 2.2))
            if anim == "rise":
                dy = 36 * (1 - smooth(lt / 1.2))
            key = json.dumps({k: line[k] for k in ("text", "font", "weight", "size", "color")}, sort_keys=True)
            spr, pad, asc = rendered_line(key, int(round(track * 1000)))
            w, h = spr.size
            if anim == "wipe":
                p = smooth(lt / 0.8)
                spr = spr.crop((0, 0, max(1, int(w * p)), h))
            if a < 1:
                al = spr.getchannel("A").point(lambda v: int(v * a))
                spr = spr.copy()
                spr.putalpha(al)
            x = int(line["x"] * W) - pad if "x" in line else (W - w) // 2
            y = int(line["y"] * H - asc / 2 - pad + dy)
            img.alpha_composite(spr, (x, max(0, y)))
    img.save(dst, compress_level=1)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    only = [int(a) for a in sys.argv[4:]]           # optional frame numbers to (re)render
    for p in OUT.glob("*.png"):
        if not only or p.name != "blank.png" and int(p.stem) in only:
            p.unlink()
    if not (OUT / "blank.png").exists():
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(OUT / "blank.png")
    with Pool(4) as pool:
        for k, _ in enumerate(pool.imap(frame, only or range(NF), chunksize=8)):
            if k % 200 == 0:
                print(f"titles {k}/{len(only) or NF}", flush=True)
    print(f"wrote {len(only) or NF} frames to {OUT}")
