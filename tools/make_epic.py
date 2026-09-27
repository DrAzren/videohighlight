"""Generate a royalty-free EPIC / inspirational trailer-style track.

120 BPM in D major, uplifting I-V-vi-IV progression (D A Bm G).
Layout in 2-second bars (26 bars = 52 s):
  bars 0-1   intro      : pulsing strings, toms, riser
  bars 2-9   rise       : drums + string ostinato + brass chords + bass
  bars 10-17 climax 1   : + choir, anthem lead, snare, crashes
  bars 18-19 breakdown  : strings + choir, big riser
  bars 20-23 final      : everything, lead an octave up
  bar  24-25 ending     : final impact hit ringing out

Usage: python3 make_epic.py OUT.wav
"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 44100
BPM = 120
BEAT = 60 / BPM
BAR = BEAT * 4
BARS = 26
N = int(BARS * BAR * SR)
rng = np.random.default_rng(3)
out_path = sys.argv[1] if len(sys.argv) > 1 else "epic.wav"


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 - 100) / (SR / 2), "low", output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), "high", output="sos"), x)


def bp(x, lo, hi):
    return sosfilt(butter(2, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos"), x)


def env(n, a, r, sustain=1.0):
    e = np.full(n, sustain)
    a_n, r_n = max(1, int(a * SR)), max(1, min(n, int(r * SR)))
    e[:a_n] *= np.linspace(0, 1, a_n)
    e[-r_n:] *= np.linspace(1, 0, r_n)
    return e


def saw(f, n, detune=(-0.08, 0, 0.08)):
    t = np.arange(n) / SR
    s = np.zeros(n)
    for d in detune:
        ff = f * 2 ** (d / 12)
        s += 2 * ((t * ff + rng.random()) % 1) - 1
    return s / len(detune)


# ---- progression (D major): D A Bm G --------------------------------------
ROOTS = [50, 45, 47, 43]                     # D3 A2 B2 G2
TRIADS = [[62, 66, 69], [61, 64, 69], [62, 66, 71], [62, 67, 71]]  # voiced near D4
# anthem melody, 8 eighth-notes per bar (None = hold)
MEL = [
    [74, None, 73, 74, 76, None, 78, None],
    [76, None, 73, None, 69, None, 71, 73],
    [74, None, 73, 71, 73, None, 74, None],
    [71, None, 74, None, 76, None, 78, None],
]

L = np.zeros(N + SR * 3)
R = np.zeros(N + SR * 3)


def add(sig, t, g=1.0, pan=0.0):
    i = int(t * SR)
    if i >= len(L):
        return
    sig = sig[: len(L) - i]
    L[i:i + len(sig)] += sig * g * (1 - max(0.0, pan))
    R[i:i + len(sig)] += sig * g * (1 + min(0.0, pan))


# ---- instruments -------------------------------------------------------------
def string_stab(f, dur):
    n = int(dur * SR)
    return lp(saw(f, n), 3500) * env(n, 0.005, dur * 0.7, 1.0) * np.exp(-np.arange(n) / SR * 6)


def brass(freqs, dur, bright=2500):
    n = int(dur * SR)
    s = sum(saw(f, n, (-0.1, -0.03, 0.04, 0.1)) for f in freqs) / len(freqs)
    s += sum(saw(f / 2, n) for f in freqs[:1]) * 0.5
    # swelling filter
    t = np.arange(n) / SR
    out = lp(s, bright) * (0.6 + 0.4 * np.minimum(1, t / 0.4))
    return out * env(n, 0.08, 0.3)


def choir(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t)
    s = np.zeros(n)
    for f in freqs:
        for d in (-0.15, 0, 0.13):
            ph = 2 * np.pi * np.cumsum(f * 2 ** (d / 12) * vib) / SR
            s += np.sign(np.sin(ph)) * 0.3 + np.sin(ph)
    s = bp(s, 400, 1300) + 0.5 * bp(s, 2200, 3200)   # "aah" formants
    return s / (len(freqs) * 3) * env(n, 0.35, 0.5)


def lead(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.3)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    s = sum(np.sin(k * ph) / k ** 1.1 for k in range(1, 9))   # horn-like
    return lp(s, 3000) * env(n, 0.04, 0.12)


def sub(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * env(n, 0.005, 0.08)


def kick():
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    f = 150 * np.exp(-t * 25) + 42
    return np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5))


def tom(pitch=90):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = pitch * (1 + 0.6 * np.exp(-t * 18))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.5)
    skin = lp(rng.standard_normal(n), 1800) * np.exp(-t * 30) * 0.5
    return np.tanh(1.6 * (body + skin))


def snare():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    nz = bp(rng.standard_normal(n), 900, 9000) * np.exp(-t * 11)
    return nz * 0.9 + np.sin(2 * np.pi * 185 * t) * np.exp(-t * 20) * 0.6


def crash(dur=3.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return hp(rng.standard_normal(n), 5000) * np.exp(-t * 1.6) * 0.8


def riser(dur):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    nz = rng.standard_normal(n)
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * t ** 2) / SR) * 0.3
    x = np.zeros(n)
    x[:] = tone
    for i in range(0, n, n // 8):
        seg = bp(nz[i:i + n // 8], 300 + 6000 * (i / n), 800 + 9000 * (i / n))
        x[i:i + len(seg)] += seg
    return x * t ** 2


def impact():
    n = int(4.0 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(60 * np.exp(-t * 3) + 30) / SR) * np.exp(-t * 1.2)
    nz = lp(rng.standard_normal(n), 2500) * np.exp(-t * 3) * 0.5
    return np.tanh(2.5 * (boom + nz))


# ---- arrangement ---------------------------------------------------------------
for bar in range(BARS):
    t0 = bar * BAR
    ci = bar % 4
    root, triad = ROOTS[ci], TRIADS[ci]
    intro = bar < 2
    rise = 2 <= bar < 10
    climax = 10 <= bar < 18
    breakdown = 18 <= bar < 20
    final = 20 <= bar < 24
    ending = bar >= 24
    full = climax or final

    if ending:
        if bar == 24:
            add(impact(), t0, 0.9)
            add(crash(4), t0, 0.35, 0.3)
            add(crash(4), t0, 0.35, -0.3)
            add(brass([hz(n) for n in [50, 57, 62, 66, 69]], BAR * 2, 1800), t0, 0.5)
            add(choir([hz(n) for n in [62, 66, 69, 74]], BAR * 2), t0, 0.5)
            add(sub(hz(38), BAR * 2), t0, 0.5)
        continue

    # string ostinato: 16ths, root-octave-fifth pattern
    pat = [0, 12, 7, 12, 0, 12, 7, 12, 0, 12, 7, 12, 0, 12, 7, 19]
    for i, p in enumerate(pat):
        acc = 1.0 if i % 4 == 0 else 0.65
        add(string_stab(hz(root + 24 + p), BEAT / 2), t0 + i * BEAT / 4,
            0.10 * acc * (0.6 if intro else 1.0), pan=(-0.35 if i % 2 else 0.35))

    if not intro:
        add(brass([hz(n) for n in triad], BAR, 1500 if rise else 3200), t0,
            0.22 if rise else 0.30)
        for e in range(8):   # driving eighth-note sub bass
            add(sub(hz(root - 12 + 12 * (root < 45)), BEAT / 2 * 0.9), t0 + e * BEAT / 2,
                0.30 if not breakdown else 0.0)

    if full or breakdown:
        add(choir([hz(n) for n in triad] + [hz(triad[0] + 12)], BAR + 0.3), t0,
            0.45 if full else 0.55)

    if full:
        up = 12 if final else 0
        mel = MEL[ci]
        for i, m in enumerate(mel):
            if m is None:
                continue
            dur = BEAT / 2
            j = i + 1
            while j < 8 and mel[j] is None:
                dur += BEAT / 2
                j += 1
            add(lead(hz(m + up), dur * 1.05), t0 + i * BEAT / 2, 0.20)

    # drums
    if intro:
        for b in range(4):
            add(tom(70), t0 + b * BEAT, 0.35 + 0.1 * b)
    elif rise:
        for b in range(4):
            add(kick(), t0 + b * BEAT, 0.55 if b in (0, 2) else 0.0)
            add(tom(95 if b % 2 else 75), t0 + b * BEAT + (BEAT / 2 if b == 3 else 0), 0.35)
        if bar % 2 == 1:
            for k in range(4):
                add(tom(120 - k * 12), t0 + 3 * BEAT + k * BEAT / 4, 0.3)
    elif full:
        for b in range(4):
            add(kick(), t0 + b * BEAT, 0.6)
            if b in (1, 3):
                add(snare(), t0 + b * BEAT, 0.38)
            add(tom(80), t0 + b * BEAT + BEAT / 2, 0.22)
        if bar % 4 == 3:
            for k in range(8):
                add(snare(), t0 + 2 * BEAT + k * BEAT / 4, 0.12 + 0.03 * k)
    elif breakdown:
        add(tom(60), t0, 0.55)
        add(brass([hz(n) for n in triad], BAR, 2200), t0, 0.25)
        if bar == 19:   # accelerating tom roll into the final climax
            for k in range(16):
                add(tom(70 + k * 4), t0 + k * BEAT / 4, 0.18 + 0.025 * k)

    # crashes / impacts at section starts
    if bar in (2, 10, 20):
        add(impact(), t0, 0.55)
        add(crash(), t0, 0.3, 0.2)
    if bar in (1, 9, 19):
        add(riser(BAR), t0, 0.22 if bar != 19 else 0.3)
    if bar == 18:
        add(riser(BAR * 2), t0, 0.12)

mix = np.stack([L, R], axis=1)[:N]
# roomy reverb: a few feedback delays
for d, g in ((0.029, 0.3), (0.043, 0.25), (0.071, 0.2), (0.113, 0.15), (0.167, 0.1)):
    k = int(d * SR)
    mix[k:, 0] += mix[:-k, 1] * g
    mix[k:, 1] += mix[:-k, 0] * g
fo = int(2.5 * SR)
mix[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
mix = np.tanh(mix / np.abs(mix).max() * 1.8) / np.tanh(1.8) * 0.95
wavfile.write(out_path, SR, (mix * 32767).astype(np.int16))
print(f"wrote {out_path} ({N / SR:.1f}s @ {BPM} BPM)")
