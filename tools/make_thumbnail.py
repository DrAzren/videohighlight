"""Build the highlight thumbnails from a graded master frame.

Usage: python3 make_thumbnail.py FRAME.png BG_FRAME.png FONT_DIR OUT_DIR

Writes OUT_DIR/thumbnail_9x16.jpg (1080x1920, Reels / TikTok / Shorts cover) and
OUT_DIR/thumbnail_16x9.jpg (1920x1080, YouTube / Facebook). Same palette as the
film: navy scrims, champagne-gold Cinzel title, ivory Cormorant / Montserrat.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FRAME, BG, FONTS, OUT = Image.open(sys.argv[1]).convert("RGB"), Image.open(sys.argv[2]).convert("RGB"), \
    Path(sys.argv[3]), Path(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)
NAVY = (8, 14, 28)
IVORY = (247, 241, 228)
CHAMPAGNE = (226, 201, 150)
GOLD = [(0.0, (250, 236, 196)), (0.45, (222, 188, 116)), (0.75, (190, 146, 74)), (1.0, (236, 210, 150))]


def font(name, weight, size):
    f = ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
    f.set_variation_by_axes([weight])
    return f


def text_layer(size, text, f, color, track=0.0):
    """RGBA sprite of tracked text with a soft navy shadow (gold = vertical gradient)."""
    sp = track * f.size
    widths = [f.getlength(c) for c in text]
    w = int(sum(widths) + sp * (len(text) - 1)) + 40
    asc, desc = f.getmetrics()
    h = asc + desc + 40
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    x = 20
    for c, cw in zip(text, widths):
        d.text((x, 20), c, font=f, fill=255)
        x += cw + sp
    if color == "gold":
        y = np.linspace(0, 1, h)
        col = np.stack([np.interp(y, [p for p, _ in GOLD], [c[k] for _, c in GOLD]) for k in range(3)], 1)
        fill = Image.fromarray(np.repeat(col[:, None, :], w, 1).astype(np.uint8))
    else:
        fill = Image.new("RGB", (w, h), color)
    spr = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh = Image.new("RGBA", (w, h), NAVY + (0,))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(f.size * 0.12)).point(lambda v: min(255, int(v * 1.1))))
    spr.alpha_composite(sh, (0, int(f.size * 0.04)))
    t = fill.convert("RGBA")
    t.putalpha(mask)
    spr.alpha_composite(t)
    return spr


def fit(text, name, weight, size, max_w, track=0.0):
    while True:
        f = font(name, weight, size)
        w = sum(f.getlength(c) for c in text) + track * size * (len(text) - 1)
        if w <= max_w or size < 20:
            return f
        size = int(size * 0.96)


def put(canvas, spr, cx=None, x=None, y=0):
    px = int(cx - spr.width / 2) if cx is not None else int(x) - 20
    canvas.alpha_composite(spr, (px, int(y) - 20))


def gradient(w, h, stops, axis=1):
    t = np.linspace(0, 1, h if axis == 1 else w)
    a = np.interp(t, [p for p, _ in stops], [v for _, v in stops])
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., :3] = NAVY
    arr[..., 3] = (a[:, None] if axis == 1 else a[None, :]) * 255
    return Image.fromarray(arr, "RGBA")


def rule(canvas, cx, y, half, alpha=230):
    ImageDraw.Draw(canvas).rectangle([cx - half, y, cx + half, y + 4], fill=(214, 178, 108, alpha))


def cover(img, w, h, cy=0.5):
    s = max(w / img.width, h / img.height)
    im = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    top = int((im.height - h) * cy)
    left = (im.width - w) // 2
    return im.crop((left, top, left + w, top + h))


def titles(c, cx, y0, max_w, scale=1.0):
    s = lambda v: int(v * scale)
    f1 = fit("FORUM INTELEKTUAL", "Cinzel", 600, s(96), max_w, 0.08)
    put(c, text_layer(None, "FORUM INTELEKTUAL", f1, "gold", 0.08), cx=cx, y=y0)
    f2 = fit("DIRAJA 2026", "Cinzel", 700, s(150), max_w, 0.14)
    put(c, text_layer(None, "DIRAJA 2026", f2, "gold", 0.14), cx=cx, y=y0 + s(108))
    rule(c, cx, y0 + s(300), s(210))
    f3 = fit("Adab dan Akal dalam Dunia Digital", "CormorantItalic", 600, s(66), max_w)
    put(c, text_layer(None, "Adab dan Akal dalam Dunia Digital", f3, CHAMPAGNE), cx=cx, y=y0 + s(330))
    f4 = fit("DR FAKRUL AZREN", "Montserrat", 700, s(52), max_w, 0.22)
    put(c, text_layer(None, "DR FAKRUL AZREN", f4, IVORY, 0.22), cx=cx, y=y0 + s(440))
    f5 = fit("9 SEPTEMBER 2026  ·  UTM JOHOR BAHRU", "Montserrat", 500, s(32), max_w, 0.2)
    put(c, text_layer(None, "9 SEPTEMBER 2026  ·  UTM JOHOR BAHRU", f5, CHAMPAGNE, 0.2), cx=cx, y=y0 + s(522))


# ---- 9:16 cover -------------------------------------------------------------------
W, H = 1080, 1920
c = cover(FRAME, W, H, 0.35).convert("RGBA")
c.alpha_composite(gradient(W, H, [(0, 0.0), (0.5, 0.0), (0.66, 0.78), (1, 0.95)]))
c.alpha_composite(gradient(W, H, [(0, 0.45), (0.12, 0.0), (1, 0.0)]))
titles(c, W / 2, 1270, W * 0.86)
c.convert("RGB").save(OUT / "thumbnail_9x16.jpg", quality=93)

# ---- 16:9 ----------------------------------------------------------------------------
W, H = 1920, 1080
c = cover(BG, W, H, 0.5).filter(ImageFilter.GaussianBlur(14)).convert("RGBA")
c.alpha_composite(Image.new("RGBA", (W, H), NAVY + (150,)))
pw = 760                                                   # portrait panel on the right
portrait = cover(FRAME, pw, H, 0.30)
panel = portrait.convert("RGBA")
ramp = np.clip(np.linspace(0, 1, pw) / 0.35, 0, 1) ** 1.5      # feathered left edge, no seam
panel.putalpha(Image.fromarray((np.repeat(ramp[None, :], H, 0) * 255).astype(np.uint8)))
c.alpha_composite(panel, (W - pw, 0))
titles(c, (W - pw) / 2 + 30, 175, (W - pw) * 0.9, scale=1.0)
c.convert("RGB").save(OUT / "thumbnail_16x9.jpg", quality=93)
print("wrote", OUT / "thumbnail_9x16.jpg", OUT / "thumbnail_16x9.jpg")
