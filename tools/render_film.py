"""Render the cinematic highlight film described by an edit list (reels/*.json).

Usage: python3 render_film.py EDL.json SRC_DIR WORK_DIR OUT.mp4 [--preview SCALE]

WORK_DIR must contain the score (EDL "music") and the typography layer in
WORK_DIR/titles (tools/make_titles.py). Pipeline:
  1. audio  - speech-enhanced, level-matched excerpts + ambience + score with gain
              automation and ducking under speech -> loudnorm -14 LUFS / -1.5 dBTP
  2. video  - per segment: ffmpeg decode (vidstab, real 60->30 fps slow motion or
              speed ramp, denoise, exposure/white-balance normalisation + shared
              warm look) -> OpenCV sub-pixel push-ins at full resolution; photos get
              a full-bleed crop or a framed layout with blurred parallax background
  3. finish - transitions in Python, then ffmpeg overlays the typography layer, adds
              vignette, fine grain and fades, and encodes H.264 High.
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps
from scipy.io import wavfile

edl = json.loads(Path(sys.argv[1]).read_text())
SRC, WORK, OUT = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
SCALE = float(sys.argv[sys.argv.index("--preview") + 1]) if "--preview" in sys.argv else 1.0
W, H = (int(edl["size"][0] * SCALE) // 2 * 2, int(edl["size"][1] * SCALE) // 2 * 2)
FPS = edl["fps"]
DUR = edl["duration"]
NF = int(round(DUR * FPS))
SR = 48000
WORK.mkdir(parents=True, exist_ok=True)
segs = edl["segments"]
for i, s in enumerate(segs):
    nxt = segs[i + 1]["trans"] if i + 1 < len(segs) else ["cut", 0]
    s["tail"] = nxt[1]                       # extra handle so the next transition can overlap
    s.setdefault("trans", ["cut", 0])

LOOK = ("eq=contrast=1.05:saturation=1.05,"
        "curves=master='0/0.015 0.2/0.175 0.5/0.5 0.8/0.825 1/0.985',"
        "colorbalance=rs=-0.015:bs=0.025:rm=0.01:bm=-0.012:rh=0.035:gh=0.012:bh=-0.035,"
        "vibrance=intensity=0.06")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stderr.decode()[-2500:]}")
    return r


def is_video(s):
    return s["src"].lower().endswith((".mp4", ".mov"))


# ---------------------------------------------------------------------------- audio
def load_audio(src, start, dur, speech):
    af = "aresample=48000,aformat=channel_layouts=stereo"
    path = SRC / src
    if src.endswith(".wav"):                 # already cleaned by tools/edit_speech.py
        path = WORK / src
    elif speech:   # hall PA + phone mic: trim rumble/hiss, gentle denoise, presence, level
        af += (",highpass=f=95,lowpass=f=9000,afftdn=nr=10:nf=-42,"
               "equalizer=f=280:t=q:w=1:g=-2.5,equalizer=f=3200:t=q:w=1.3:g=3,"
               "acompressor=threshold=-24dB:ratio=2.5:attack=8:release=160:makeup=2")
    r = run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", str(path),
             "-af", af, "-f", "f32le", "-"])
    x = np.frombuffer(r.stdout, np.float32).reshape(-1, 2).astype(np.float64)
    rms = np.sqrt((x ** 2).mean()) + 1e-9
    return x * (10 ** (-20 / 20) / rms)        # every event normalised to -20 dBFS RMS


def mix_audio():
    n = int((DUR + 0.5) * SR)
    voice = np.zeros((n, 2))
    duck = np.ones(n)
    t = np.arange(n) / SR
    for ev in edl["audio"]:
        x = load_audio(ev["src"], ev["in"], ev["dur"], ev.get("speech", False)) * ev.get("gain", 1.0)
        fi, fo = ev.get("fade", [0.05, 0.1])
        e = np.ones(len(x))
        a, b = max(1, int(fi * SR)), max(1, int(fo * SR))
        e[:a] = np.linspace(0, 1, a) ** 2
        e[-b:] *= np.linspace(1, 0, b) ** 2
        i = int(ev["at"] * SR)
        m = min(len(x), n - i)
        voice[i:i + m] += (x * e[:, None])[:m]
        if ev.get("speech"):
            lvl = ev.get("duck", 0.2)
            t0, t1 = ev["at"], ev["at"] + ev["dur"]
            ramp = np.clip(np.minimum((t - (t0 - 0.3)) / 0.3, ((t1 + 0.6) - t) / 0.6), 0, 1)
            duck = np.minimum(duck, 1 - (1 - lvl) * ramp)
    sr, mus = wavfile.read(WORK / edl["music"])
    mus = mus.astype(np.float64) / 32768
    mus = np.pad(mus, ((0, max(0, n - len(mus))), (0, 0)))[:n]
    pts = np.array(edl["music_gain"])
    auto = np.interp(t, pts[:, 0], pts[:, 1])
    # music sits at roughly -10 dBFS RMS in loud passages; speech at -20 dBFS stays on top once ducked
    mix = voice * 1.0 + mus * (auto * duck)[:, None] * 0.75
    fo = int(1.2 * SR)
    end = int(DUR * SR)
    mix[end - fo:end] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    mix = mix[:end]
    raw = WORK / "mix_raw.wav"
    wavfile.write(raw, SR, (np.clip(mix, -1, 1) * 32767).astype(np.int16))
    # two-pass loudness normalisation
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    st = json.loads(r.stderr[r.stderr.rindex("{"):])
    run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af",
         f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:"
         f"measured_LRA={st['input_lra']}:measured_thresh={st['input_thresh']}:"
         f"offset={st['target_offset']}:linear=true,aresample=48000",
         "-c:a", "pcm_s24le", str(WORK / "mix.wav")])
    print(f"audio: mixed {len(edl['audio'])} events, measured {st['input_i']} LUFS -> -14", flush=True)


# ---------------------------------------------------------------------------- grading
def sample_frame(s):
    if is_video(s):
        r = run(["ffmpeg", "-v", "error", "-ss", str(s["in"] + 0.5), "-i", str(SRC / s["src"]),
                 "-frames:v", "1", "-vf", "scale=270:480", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        return np.frombuffer(r.stdout, np.uint8).reshape(480, 270, 3) / 255.0
    im = ImageOps.exif_transpose(Image.open(SRC / s["src"])).convert("RGB")
    im.thumbnail((480, 480))
    return np.asarray(im) / 255.0


def correction(s):
    """Partial exposure + white-balance normalisation measured on near-neutral pixels."""
    if not is_video(s):
        return ""                               # official photos are already well graded
    x = sample_frame(s)
    lum = x @ [0.2126, 0.7152, 0.0722]
    mx, mn = x.max(2), x.min(2)
    sat = (mx - mn) / (mx + 1e-6)
    neutral = (sat < 0.22) & (lum > 0.18) & (lum < 0.88)
    gains = [1.0, 1.0, 1.0]
    if neutral.sum() > 300:
        ch = x[neutral].mean(0)
        g = (ch.mean() / ch) ** 0.55
        gains = list(np.clip(g / g[1], 0.88, 1.14))
    m = float(np.clip(np.median(lum), 0.05, 0.95))
    gamma = float(np.clip((math.log(m) / math.log(0.44)) ** 0.55, 0.88, 1.22))
    return (f"colorchannelmixer=rr={gains[0]:.3f}:gg={gains[1]:.3f}:bb={gains[2]:.3f},"
            f"eq=gamma={gamma:.3f},")


# ---------------------------------------------------------------------------- readers
def src_span(s):
    total = s["dur"] + s["tail"]
    if "ramp" in s:
        s0, s1 = s["ramp"]
        return s0 * total + (s1 - s0) * total / 2
    return total * s.get("speed", 1.0)


def speed_filter(s):
    total = s["dur"] + s["tail"]
    if "ramp" in s:
        # output-time speed v(T) = s0 + (s1-s0) T/total  =>  src(T) = s0 T + a T^2,  invert for setpts
        s0, s1 = s["ramp"]
        a = (s1 - s0) / (2 * total)
        return f"setpts=PTS-STARTPTS,setpts='(-{s0}+sqrt({s0}*{s0}+4*{a}*T))/(2*{a})/TB'"
    return f"setpts=(PTS-STARTPTS)/{s.get('speed', 1.0)}"


class VideoReader:
    def __init__(self, s, idx):
        span = src_span(s) + 0.25
        stab = ""
        if s.get("stab", True):
            trf = WORK / f"stab_{idx:02d}.trf"
            if not trf.exists():
                run(["ffmpeg", "-v", "error", "-ss", str(s["in"]), "-t", str(span), "-i", str(SRC / s["src"]),
                     "-vf", f"vidstabdetect=shakiness=5:accuracy=15:result={trf}", "-f", "null", "-"])
            stab = f"vidstabtransform=input={trf}:smoothing=20:optzoom=1:interpol=bicubic,"
        vf = (f"{stab}{speed_filter(s)},fps={FPS},hqdn3d=1.5:1.5:3:3,cas=strength=0.3,"
              f"{correction(s)}{LOOK},format=rgb24")
        probe = run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                     "stream=width,height:stream_side_data=rotation", "-of", "json", str(SRC / s["src"])])
        st = json.loads(probe.stdout)["streams"][0]
        rot = next((abs(int(d.get("rotation", 0))) for d in st.get("side_data_list", []) if "rotation" in d), 0)
        self.w, self.h = (st["height"], st["width"]) if rot % 180 == 90 else (st["width"], st["height"])
        self.p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(s["in"]), "-t", str(span),
                                   "-i", str(SRC / s["src"]), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24",
                                   "-"], stdout=subprocess.PIPE)
        self.last = None

    def read(self):
        buf = self.p.stdout.read(self.w * self.h * 3)
        if len(buf) == self.w * self.h * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
        return self.last

    def close(self):
        self.p.stdout.close()
        self.p.kill()


class PhotoReader:
    def __init__(self, s, idx):
        im = ImageOps.exif_transpose(Image.open(SRC / s["src"])).convert("RGB")
        if "trim" in s:                          # [left, top, right, bottom] fractions, e.g. drop a watermark
            l, t, r, b = s["trim"]
            im = im.crop((int(l * im.width), int(t * im.height), int((1 - r) * im.width), int((1 - b) * im.height)))
        tmp = WORK / f"photo_{idx:02d}.png"
        im.save(tmp)
        r = run(["ffmpeg", "-v", "error", "-i", str(tmp), "-vf", f"{LOOK},format=rgb24",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
        self.img = np.frombuffer(r.stdout, np.uint8).reshape(im.height, im.width, 3)
        self.h, self.w = self.img.shape[:2]
        if s.get("layout") == "framed":
            # blurred, darkened cover background (computed once)
            k = H / self.h
            small = cv2.resize(self.img, (int(self.w * k / 6), int(H / 6)), interpolation=cv2.INTER_AREA)
            small = cv2.GaussianBlur(small, (0, 0), 9)
            hsv = cv2.cvtColor(small, cv2.COLOR_RGB2HSV).astype(np.float32)
            hsv[..., 1] *= 0.7
            hsv[..., 2] *= 0.42
            self.bg = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2RGB)

    def read(self):
        return self.img

    def close(self):
        pass


def ease(p):
    return p * p * (3 - 2 * p)


def place(src, s, T):
    """Warp a source frame to the W x H canvas with the segment's push-in at local time T."""
    total = s["dur"] + s["tail"]
    z0, z1 = s.get("zoom", [1.0, 1.0])
    z = z0 + (z1 - z0) * ease(min(1.0, T / total)) if total > 0 else z0
    h, w = src.shape[:2]
    punch = s.get("punch", 1.0)
    if s.get("layout") == "framed":
        return framed(src, s, z)
    sc = max(W / w, H / h) * punch * z
    vw, vh = W / sc, H / sc                       # visible window in source pixels
    cx = min(max(s.get("cx", 0.5) * w, vw / 2), w - vw / 2)
    cy = min(max(s.get("cy", 0.5) * h, vh / 2), h - vh / 2)
    M = np.float32([[sc, 0, W / 2 - sc * cx], [0, sc, H / 2 - sc * cy]])
    return cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)


READERS = {}


def framed(src, s, z):
    rd = READERS[id(s)]
    bg = rd.bg
    bh, bw = bg.shape[:2]
    zb = 1.1 - (z - 1.0) * 0.6                     # background drifts against the foreground
    sc = max(W / bw, H / bh) * zb
    M = np.float32([[sc, 0, W / 2 - sc * bw / 2], [0, sc, H / 2 - sc * bh / 2]])
    canvas = cv2.warpAffine(bg, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    h, w = src.shape[:2]
    fw = W * 0.94 * z
    sc = fw / w
    fh = h * sc
    cy = H * 0.46
    M = np.float32([[sc, 0, W / 2 - fw / 2], [0, sc, cy - fh / 2]])
    fg = cv2.warpAffine(src, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
    mask = cv2.warpAffine(np.full((h, w), 255, np.uint8), M, (W, H), flags=cv2.INTER_LINEAR)
    # soft shadow + champagne keyline
    sh = cv2.GaussianBlur(mask, (0, 0), 18 * SCALE + 1)
    canvas = (canvas.astype(np.float32) * (1 - sh[..., None] / 255 * 0.55)).astype(np.uint8)
    m = mask[..., None] / 255.0
    canvas = (canvas * (1 - m) + fg * m).astype(np.uint8)
    x0, y0 = int(W / 2 - fw / 2), int(cy - fh / 2)
    cv2.rectangle(canvas, (x0 - 3, y0 - 3), (int(x0 + fw) + 2, int(y0 + fh) + 2), (214, 184, 120),
                  max(1, int(3 * SCALE)))
    return canvas


def transition(kind, a, b, p):
    p = ease(p)
    if kind == "smoothleft":                       # restrained whip with motion blur
        off = int(W * p)
        out = np.empty_like(a)
        out[:, :W - off] = a[:, off:]
        out[:, W - off:] = b[:, :off]
        k = int(1 + 160 * SCALE * math.sin(math.pi * p))
        return cv2.blur(out, (k, 1)) if k > 2 else out
    return cv2.addWeighted(a, 1 - p, b, p, 0)


# ---------------------------------------------------------------------------- video
def render():
    titles = WORK / "titles"
    vf = [f"[0:v]vignette=angle=PI/5.5:mode=forward[v0]"]
    if SCALE != 1.0:
        vf.append(f"[1:v]scale={W}:{H}[t]")
        tl = "[t]"
    else:
        tl = "[1:v]"
    fi = edl.get("fade_in", 0.8)
    fo = edl.get("fade_out", [DUR - 1, 1])
    vf.append(f"[v0]{tl}overlay=0:0:format=auto,noise=c0s={6 if SCALE == 1 else 4}:c0f=t,"
              f"fade=t=in:st=0:d={fi},fade=t=out:st={fo[0]}:d={fo[1]},format=yuv420p[v]")
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-framerate", str(FPS), "-i", str(titles / "%05d.png"), "-i", str(WORK / "mix.wav"),
         "-filter_complex", ";".join(vf), "-map", "[v]", "-map", "2:a",
         "-c:v", "libx264", "-preset", "slow" if SCALE == 1 else "veryfast", "-crf", "15",
         "-profile:v", "high", "-level:v", "5.1" if SCALE == 1 else "4.1",
         "-x264-params", "aq-mode=3:deblock=-1,-1", "-maxrate", "60M" if SCALE == 1 else "20M", "-bufsize", "120M",
         "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
         "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", f"{DUR:.3f}", "-movflags", "+faststart",
         str(OUT)], stdin=subprocess.PIPE)

    def reader(i):
        s = segs[i]
        if id(s) not in READERS:
            READERS[id(s)] = (VideoReader if is_video(s) else PhotoReader)(s, i)
            print(f"segment {i + 1}/{len(segs)}  {s['src']}  at {s['at']:.2f}s", flush=True)
        return READERS[id(s)]

    for f in range(NF):
        t = f / FPS
        # the active segment, plus the next one while its transition overlaps
        i = max(k for k, s in enumerate(segs) if s["at"] <= t + 1e-6)
        s = segs[i]
        frame = place(reader(i).read(), s, t - s["at"])
        if i > 0 and segs[i - 1]["tail"] > 0 and t < s["at"] + s["trans"][1]:
            prev = segs[i - 1]
            pf = place(reader(i - 1).read(), prev, t - prev["at"])
            frame = transition(s["trans"][0], pf, frame, (t - s["at"]) / s["trans"][1])
        elif i > 0 and id(segs[i - 1]) in READERS:
            READERS.pop(id(segs[i - 1])).close()
        enc.stdin.write(np.ascontiguousarray(frame).tobytes())
    enc.stdin.close()
    if enc.wait():
        sys.exit("encoder failed")
    for r in READERS.values():
        r.close()
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    if "--video-only" not in sys.argv:
        mix_audio()
    if "--audio-only" not in sys.argv:
        render()
