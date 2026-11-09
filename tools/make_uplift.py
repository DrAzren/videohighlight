"""Generate a royalty-free, warm & uplifting instrumental with light percussion.

120 BPM (1 bar = 2 s, so 1-2 s montage cuts land on beats), D major,
I-V-vi-IV progression (D A Bm G). Built bar-by-bar so the edit can sit on the grid.

Sections (bars, from the music start):
  0-1   intro    : pad swell, plucked arpeggio, shaker, riser into bar 2
  2-10  groove   : + kick, clap, bass pulse, brighter pluck
  11-17 chorus   : + bell lead hook, open hats, fuller pad
  18-20 outro    : half-time kick, felt piano, pad (slower, warmer)
  21    ending   : final D major chord ringing out under the tail

Usage: python3 make_uplift.py OUT.wav [LEAD_IN_SECONDS]
  LEAD_IN_SECONDS of silence is prepended (e.g. the stage-audio hook length) so
  bar 0 of the music lands exactly where the hook sentence ends.
"""
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100
BPM = 120
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = 22
TAIL = 3.0
out_path = sys.argv[1] if len(sys.argv) > 1 else "uplift.wav"
lead_in = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
N = int((BARS * BAR + TAIL) * SR)
rng = np.random.default_rng(11)

L = np.zeros(N)
R = np.zeros(N)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, f, order=2):
    return sosfilt(butter(order, f, "low", fs=SR, output="sos"), x)


def hp(x, f, order=2):
    return sosfilt(butter(order, f, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo, hi], "band", fs=SR, output="sos"), x)


def add(sig, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N:
        return
    sig = sig[: N - i]
    gl = gain * np.cos((pan + 1) * np.pi / 4)
    gr = gain * np.sin((pan + 1) * np.pi / 4)
    L[i:i + len(sig)] += sig * gl
    R[i:i + len(sig)] += sig * gr


def env(n, a, d, s=0.0, r=0.0):
    """attack/decay(exp)/sustain level, linear release at the end (seconds)."""
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    if r > 0:
        rn = int(r * SR)
        e[-rn:] *= np.linspace(1, 0, rn)
    return e


# ---------- instruments ----------
def kick(vel=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    click = lp(rng.standard_normal(n), 3500) * np.exp(-t * 180) * 0.35
    return np.tanh((body + click) * 1.6) * 0.8 * vel


def clap(vel=1.0):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = bp(rng.standard_normal(n), 900, 5200)
    e = np.zeros(n)
    for k, off in enumerate((0.0, 0.011, 0.022)):
        e += (t >= off) * np.exp(-np.clip(t - off, 0, None) * (160 if k < 2 else 22))
    return noise * e * 0.55 * vel


def shaker(vel=1.0):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    noise = hp(rng.standard_normal(n), 6500)
    return noise * (np.minimum(t / 0.012, 1) * np.exp(-t * 55)) * 0.22 * vel


def hat(open_=False, vel=1.0):
    n = int((0.35 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    noise = hp(rng.standard_normal(n), 8000)
    return noise * np.exp(-t * (12 if open_ else 70)) * 0.2 * vel


def pluck(m, dur=0.5, bright=0.5):
    """Karplus-Strong plucked string."""
    f = hz(m)
    n = int(dur * SR)
    p = int(SR / f)
    buf = rng.uniform(-1, 1, p)
    buf = lp(buf, 2000 + 6000 * bright)
    out = np.zeros(n)
    for i in range(n):
        out[i] = buf[i % p]
        buf[i % p] = 0.5 * (buf[i % p] + buf[(i + 1) % p]) * 0.996
    return out * env(n, 0.002, dur * 0.6, 0, 0.03) * 0.5


def saw(f, n, detune=0.0):
    t = np.arange(n) / SR
    ph = (f * (1 + detune)) * t + rng.random()
    return 2 * (ph % 1) - 1


def pad(notes, dur, bright=900):
    n = int(dur * SR)
    x = np.zeros(n)
    for m in notes:
        for d in (-0.006, 0.0, 0.007):
            x += saw(hz(m), n, d)
    x = lp(x / (len(notes) * 3), bright, 2)
    return x * env(n, 0.45, 99, 1.0, 0.5) * 0.55


def bass(m, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    x = np.sin(2 * np.pi * f * t) + 0.35 * lp(saw(f, n), 600)
    return np.tanh(x * 1.3) * env(n, 0.005, 0.25, 0.55, 0.04) * 0.42


def bell(m, dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    x = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
         + 0.25 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 9))
    return x * env(n, 0.004, 0.45, 0, 0.05) * 0.26


def piano(m, dur=1.8, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    x = sum(a * np.sin(2 * np.pi * k * f * t * (1 + 0.0004 * k)) * np.exp(-t * (1.6 + k * 0.9))
            for k, a in ((1, 1.0), (2, 0.45), (3, 0.2), (4, 0.1)))
    x = lp(x, 3200)
    return x * env(n, 0.003, 99, 1.0, 0.25) * 0.3 * vel


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    seg = 2048
    for i in range(0, n, seg):
        fc = 400 + 7000 * (i / n) ** 2
        out[i:i + seg] = bp(noise[i:i + seg + 0], fc * 0.7, min(fc * 1.4, SR / 2 - 100))[: len(out[i:i + seg])]
    return out * (t / dur) ** 2 * 0.25


# ---------- harmony ----------
D, A, Bm, G = 50, 45, 47, 43            # bass roots
CHORDS = {D: [62, 66, 69], A: [61, 64, 69], Bm: [62, 66, 71], G: [59, 62, 67]}
PROG = [D, A, Bm, G]
ARP = [0, 1, 2, 1, 2, 0, 1, 2]           # chord-tone index per 8th note
LEAD = [  # bell hook, (beat offset, midi, dur) per bar of the 4-bar loop
    [(0, 78, 1.0), (1.5, 76, 0.5), (2, 74, 1.0), (3, 76, 1.0)],
    [(0, 76, 1.0), (1.5, 73, 0.5), (2, 69, 1.5)],
    [(0, 74, 1.0), (1.5, 76, 0.5), (2, 78, 1.0), (3, 81, 1.0)],
    [(0, 79, 1.5), (2, 78, 0.5), (2.5, 76, 0.5), (3, 74, 1.0)],
]

for b in range(BARS):
    t0 = b * BAR
    root = PROG[b % 4]
    ch = CHORDS[root]
    intro, groove, chorus = b < 2, 2 <= b < 11, 11 <= b < 18
    outro, ending = 18 <= b < 21, b >= 21

    if ending:
        if b == 21:
            add(pad([62, 66, 69, 74], BAR + TAIL, 1100), t0, 0.9)
            for k, m in enumerate([50, 62, 66, 69, 74, 78]):
                add(piano(m, BAR + TAIL, 0.9), t0 + k * 0.06, 0.8, (k - 2.5) * 0.15)
            add(kick(0.7), t0, 0.6)
        continue

    # pad
    add(pad(ch, BAR + 0.4, 700 if intro else 1300 if chorus else 1000), t0,
        0.55 if intro else 0.42 if outro else 0.38)

    # plucked arpeggio (8ths); a 16th pickup in the chorus
    if not outro:
        for k in range(8):
            m = ch[ARP[k]] + (12 if chorus and k % 4 == 3 else 0)
            add(pluck(m, 0.55, 0.35 if intro else 0.6), t0 + k * BEAT / 2,
                0.42 if intro else 0.36, -0.35 if k % 2 else 0.35)

    # felt piano in the outro (slower: quarter-note broken chords)
    if outro:
        for k, idx in enumerate([0, 1, 2, 1]):
            add(piano(ch[idx] + 12, 1.6), t0 + k * BEAT, 0.65, (idx - 1) * 0.3)
        add(piano(root + 12, BAR * 1.2), t0, 0.5)

    # bass
    if groove or chorus:
        for k in range(8):
            if k in (0, 3, 4, 6, 7):
                add(bass(root - 12 + (12 if k == 7 and chorus else 0), BEAT * 0.48), t0 + k * BEAT / 2, 0.9)
    if outro:
        add(bass(root - 12, BAR * 0.95), t0, 0.7)

    # drums
    if groove or chorus:
        for k in range(4):
            add(kick(1.0 if k == 0 else 0.85), t0 + k * BEAT, 0.85)
        for k in (1, 3):
            add(clap(), t0 + k * BEAT, 0.7)
        for k in range(16):
            add(shaker(1.0 if k % 2 else 0.6), t0 + k * BEAT / 4, 0.8, 0.3)
        if chorus:
            for k in range(4):
                add(hat(True, 0.8), t0 + k * BEAT + BEAT / 2, 0.55, -0.3)
    if intro:
        for k in range(8):
            add(shaker(0.5 + 0.5 * (k % 2)), t0 + k * BEAT / 2, 0.55 + 0.25 * b, 0.3)
    if outro:
        add(kick(0.75), t0, 0.7)
        add(clap(0.7), t0 + 2 * BEAT, 0.5)
        for k in range(8):
            add(shaker(0.5), t0 + k * BEAT / 2, 0.45, 0.3)

    # bell lead hook in the chorus
    if chorus:
        for off, m, du in LEAD[(b - 11) % 4]:
            add(bell(m, du * BEAT + 0.6), t0 + off * BEAT, 0.9, 0.15)

    # transitions
    if b == 1:
        add(riser(BAR), t0, 0.8)
    if b == 10:
        add(riser(BAR), t0, 0.6)
        add(clap(0.6), t0 + 3.5 * BEAT, 0.5)
    if b in (2, 11):  # crash-ish swell on the downbeat
        add(hat(True, 1.0), t0, 0.9)
        add(hat(True, 1.0), t0, 0.9, 0.4)

# ---------- mix bus ----------
ir_n = int(2.2 * SR)
tt = np.arange(ir_n) / SR
irL = rng.standard_normal(ir_n) * np.exp(-tt * 3.2)
irR = rng.standard_normal(ir_n) * np.exp(-tt * 3.2)
irL, irR = lp(irL, 5000), lp(irR, 5000)
irL /= np.sqrt(np.sum(irL ** 2))
irR /= np.sqrt(np.sum(irR ** 2))
wetL = fftconvolve(L, irL)[:N]
wetR = fftconvolve(R, irR)[:N]
L2, R2 = L + 0.22 * wetL, R + 0.22 * wetR
mix = np.stack([L2, R2], 1)
mix = hp(mix.T, 30).T
mix = np.tanh(mix * 1.2) / np.tanh(1.2)
mix /= np.max(np.abs(mix)) + 1e-9
mix *= 0.89
fade = int(1.5 * SR)
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
if lead_in > 0:
    mix = np.concatenate([np.zeros((int(lead_in * SR), 2)), mix])
wavfile.write(out_path, SR, (mix * 32767).astype(np.int16))
print(f"wrote {out_path}: {len(mix) / SR:.2f}s (music bar 0 at {lead_in:.2f}s, bar={BAR}s)")
