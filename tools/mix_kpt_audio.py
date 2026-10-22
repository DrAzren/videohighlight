"""Mix the KPT reel soundtrack: music bed + synthesised sound design cued to the motion
graphics + Dr Azren's real speech excerpt (cleaned, with the music ducked under it).

Usage: python3 mix_kpt_audio.py MUSIC.wav SPEECH_SRC.mp4 OUT.wav
"""
import subprocess
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
LEN = 30.0
N = int(LEN * SR)
rng = np.random.default_rng(5)
music_path, speech_src, out_path = sys.argv[1:4]

# speech excerpt: source 17.35-18.55 s of the stage clip ("Kita validate emosi kita.")
SPEECH_IN, SPEECH_OUT, SPEECH_AT = 17.35, 18.55, 12.75


def filt(x, kind, fc, order=2):
    wn = [f / (SR / 2) for f in fc] if kind == "band" else min(fc, SR / 2 - 200) / (SR / 2)
    return sosfilt(butter(order, wn, kind, output="sos"), x)


def env_ad(n, a, d):
    t = np.arange(n) / SR
    e = np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-np.maximum(t - a, 0) / d)
    return e


# ---- sound effects ----------------------------------------------------------
def whoosh(dur=0.32, up=True, g=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = rng.standard_normal(n)
    out = np.zeros(n)
    steps = 16
    for k in range(steps):
        a, b = k * n // steps, (k + 1) * n // steps
        x = k / steps if up else 1 - k / steps
        fc = 400 * (12 ** x)
        out[a:b] = filt(nz, "band", (fc * .6, min(fc * 1.6, 18000)))[a:b]
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return out * e * 0.9 * g


def pop(f=700, g=1.0):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * np.cumsum(f * (1 + 1.2 * np.exp(-t / 0.012))) / SR
    s = np.sin(ph) * np.exp(-t / 0.035)
    click = filt(rng.standard_normal(n), "high", 3000) * np.exp(-t / 0.002) * 0.3
    return (s + click) * 0.6 * g


def click(g=1.0):
    n = int(0.03 * SR)
    t = np.arange(n) / SR
    return filt(rng.standard_normal(n), "band", (2000, 9000)) * np.exp(-t / 0.003) * 0.7 * g


def shutter(g=1.0):
    n = int(0.22 * SR)
    out = np.zeros(n)
    for off, a in ((0.0, 1.0), (0.07, 0.8)):
        i = int(off * SR)
        m = n - i
        tt = np.arange(m) / SR
        out[i:] += filt(rng.standard_normal(m), "band", (1500, 8000)) * np.exp(-tt / 0.012) * a
        out[i:] += np.sin(2 * np.pi * 180 * tt) * np.exp(-tt / 0.01) * 0.4 * a
    return out * 0.6 * g


def rip(dur=0.38, g=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = filt(rng.standard_normal(n), "band", (700, 6000))
    crackle = (rng.random(n) < 0.02).astype(float)
    crackle = np.convolve(crackle, np.exp(-np.arange(200) / 30), "same")
    am = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 38 * t + rng.random() * 6))
    e = np.clip(t / 0.03, 0, 1) * np.exp(-np.maximum(t - 0.12, 0) / 0.12)
    return (nz * am + crackle * 0.6) * e * 0.8 * g


def paper(dur=0.25, g=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = filt(rng.standard_normal(n), "band", (500, 4000))
    am = 0.5 + 0.5 * np.sin(2 * np.pi * 22 * t) ** 2
    return nz * am * np.sin(np.pi * t / dur) * 0.5 * g


def thud(g=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * (55 + 90 * np.exp(-t / 0.03)) * t) * np.exp(-t / 0.16)
    k = filt(rng.standard_normal(n), "band", (300, 3000)) * np.exp(-t / 0.02) * 0.5
    return np.tanh(1.8 * (s + k)) * 0.8 * g


def shimmer(dur=0.9, g=1.0):
    n = int(dur * SR)
    out = np.zeros(n)
    for k in range(9):
        f = 2200 * 2 ** (rng.integers(0, 12) / 12) * (2 if k % 3 == 0 else 1)
        i = int(k * 0.05 * SR)
        m = n - i
        tt = np.arange(m) / SR
        out[i:] += np.sin(2 * np.pi * f * tt) * np.exp(-tt / 0.18) * 0.25
    return out * g


CUES = [
    (0.04, pop(520, 1.0)), (0.06, paper(0.3, 0.8)),
    *[(0.06 + i * 0.09, click(0.6)) for i in range(7)],
    (0.55, thud(1.0)),
    (1.38, whoosh(0.28, True, 0.9)),
    (1.55, paper(0.3, 0.9)), *[(1.62 + i * 0.06, click(0.35)) for i in range(8)],
    (2.7, whoosh(0.3, False, 0.6)),
    (2.85, paper(0.18, 0.7)), (3.0, rip(0.4, 1.0)),
    (3.3, pop(640, 1.0)), *[(3.5 + i * 0.12, pop(700 + i * 90, 0.7)) for i in range(6)],
    (4.88, whoosh(0.25, True, 0.8)),
    (5.25, pop(800, 0.7)), (5.5, pop(900, 0.7)), (5.75, pop(1000, 0.7)),
    (6.95, shutter(1.0)), (7.18, shimmer(0.8, 0.8)),
    (8.7, whoosh(0.3, False, 0.6)),
    (8.82, whoosh(0.2, True, 0.7)),
    *[(9.16 + i * 0.04, click(0.4)) for i in range(9)], (9.62, pop(760, 0.9)), (9.85, paper(0.3, 0.9)),
    (10.38, whoosh(0.26, True, 0.85)),
    (12.05, whoosh(0.35, False, 0.35)),
    (13.86, whoosh(0.28, True, 0.6)),
    (14.12, pop(900, 0.5)), (14.27, pop(1000, 0.5)), (14.42, pop(1100, 0.5)),
    (14.5, thud(0.45)), (15.0, thud(0.45)), (15.5, thud(0.5)),
    (16.48, shutter(1.0)), (16.52, whoosh(0.4, True, 0.5)),
    (16.83, paper(0.17, 0.8)), (17.0, rip(0.42, 1.0)),
    (17.12, pop(980, 0.6)), (17.22, pop(1180, 0.5)),
    (17.88, whoosh(0.26, True, 0.85)), (18.05, pop(880, 0.5)), (18.15, pop(1050, 0.5)),
    (18.9, whoosh(0.3, False, 0.7)), *[(19.18 + i * 0.04, click(0.35)) for i in range(10)],
    (19.4, pop(700, 0.6)), (19.5, pop(820, 0.6)),
    (20.35, whoosh(0.28, True, 0.8)), (20.98, shutter(0.9)), (21.0, thud(1.0)),
    (21.38, whoosh(0.26, True, 0.85)),
    (22.5, whoosh(0.3, False, 0.5)),
    (22.55, shutter(0.8)), (22.6, paper(0.25, 0.8)),
    (22.8, shutter(0.8)), (22.85, paper(0.25, 0.8)),
    (23.05, shutter(0.8)), (23.1, paper(0.25, 0.8)),
    (23.8, whoosh(0.35, True, 0.6)),
    (24.4, shimmer(1.2, 0.7)),
    (26.45, whoosh(0.6, False, 0.45)),
    (27.25, shimmer(1.4, 0.8)), (28.4, shimmer(1.0, 0.6)),
]

sfx = np.zeros(N + SR)
for t, s in CUES:
    i = int(t * SR)
    sfx[i:i + len(s)] += s[: len(sfx) - i]
sfx = sfx[:N]
sfx_st = np.stack([sfx, sfx]) * 0.42

# ---- music with ducking under speech ------------------------------------------
sr_m, m = wavfile.read(music_path)
assert sr_m == SR
m = m.astype(float).T / 32768
m = m[:, :N]
if m.shape[1] < N:
    m = np.pad(m, ((0, 0), (0, N - m.shape[1])))
tt = np.arange(N) / SR
duck = 1 - 0.62 * np.clip(np.minimum((tt - 12.5) / 0.15, (14.0 - tt) / 0.2), 0, 1)
m *= duck

# ---- speech excerpt: high-pass, de-noise, gentle compression ------------------
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-ss", str(SPEECH_IN), "-t", f"{SPEECH_OUT - SPEECH_IN:.2f}",
     "-i", speech_src, "-af",
     "highpass=f=90,lowpass=f=9000,afftdn=nf=-30:nr=14,"
     "equalizer=f=3000:t=q:w=1.2:g=3,acompressor=threshold=-22dB:ratio=3:attack=5:release=80,"
     "loudnorm=I=-16:TP=-2:LRA=7",
     "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, check=True).stdout
v = np.frombuffer(raw, np.int16).astype(float) / 32768
fi, fo = int(0.03 * SR), int(0.12 * SR)
v[:fi] *= np.linspace(0, 1, fi)
v[-fo:] *= np.linspace(1, 0, fo)
voice = np.zeros(N)
i = int(SPEECH_AT * SR)
voice[i:i + len(v)] = v[: N - i]
voice_st = np.stack([voice, voice]) * 1.25

mix = m * 0.9 + sfx_st + voice_st
peak = np.max(np.abs(mix))
mix = mix / max(peak, 1e-9) * 0.95
wavfile.write(out_path, SR, (mix.T * 32767).astype(np.int16))
print(f"wrote {out_path} (pre-normalise peak {peak:.2f})")
