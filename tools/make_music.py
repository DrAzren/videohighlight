"""Generate a royalty-free, uplifting cinematic backing track (no copyright issues).

Structure (at 84 BPM, 4/4): soft piano intro -> pads + bass enter -> drums build ->
full chorus -> gentle outro. Progression: vi - IV - I - V (Am F C G), a classic
"inspirational" progression.

Usage: python3 make_music.py OUT.wav [SECONDS]
"""
import sys
import numpy as np
from scipy.signal import butter, lfilter

SR = 44100
BPM = 84
BEAT = 60.0 / BPM
BAR = BEAT * 4

out_path = sys.argv[1] if len(sys.argv) > 1 else "music.wav"
total = float(sys.argv[2]) if len(sys.argv) > 2 else 58.0
N = int(total * SR)
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# chords as MIDI notes (root position around middle C)
CHORDS = [
    [57, 60, 64],  # Am
    [53, 57, 60],  # F
    [48, 52, 55],  # C
    [55, 59, 62],  # G
]
BASS = [45, 41, 48, 43]
MELODY = [  # one note per beat over 4 bars, repeated with variation
    [76, 74, 72, 74], [72, 69, 72, 74], [76, 79, 76, 74], [74, 71, 74, 79],
]


def env_adsr(n, a=0.01, d=0.3, s=0.4, r=0.6):
    t = np.arange(n) / SR
    e = np.ones(n) * s
    a_n, d_n = int(a * SR), int(d * SR)
    e[:a_n] = np.linspace(0, 1, a_n)
    e[a_n:a_n + d_n] = np.linspace(1, s, min(d_n, max(0, n - a_n)))
    r_n = min(int(r * SR), n)
    e[-r_n:] *= np.linspace(1, 0, r_n)
    return e


def piano(freq, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * freq * k * t) / k ** 1.6 * np.exp(-t * (1.5 + k * 0.8))
               for k in range(1, 7))
    return vel * tone * env_adsr(n, 0.004, 0.2, 0.5, 0.3)


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            ff = f * 2 ** (det / 12)
            sig += np.sin(2 * np.pi * ff * t + rng.uniform(0, 6.28)) * 0.5
            sig += np.sin(2 * np.pi * ff * 2 * t) * 0.12
    return sig / (len(freqs) * 3) * env_adsr(n, 0.8, 0.5, 0.9, 0.8)


def bass(freq, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(4 * np.pi * freq * t)) * env_adsr(n, 0.01, 0.4, 0.7, 0.2)


def kick():
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 18) + 45
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7)


def snare():
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    b, a = butter(2, [1500 / (SR / 2), 8000 / (SR / 2)], btype="band")
    noise = lfilter(b, a, rng.standard_normal(n))
    return (noise * 0.8 + 0.4 * np.sin(2 * np.pi * 190 * t)) * np.exp(-t * 16)


def hat():
    n = int(0.08 * SR)
    b, a = butter(2, 7000 / (SR / 2), btype="high")
    return lfilter(b, a, rng.standard_normal(n)) * np.exp(-np.arange(n) / SR * 60)


def riser(dur):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    b, a = butter(2, 3000 / (SR / 2), btype="high")
    return lfilter(b, a, rng.standard_normal(n)) * t ** 2.5


L = np.zeros(N + SR * 2)
R = np.zeros(N + SR * 2)


def add(sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= len(L):
        return
    sig = sig[: len(L) - i]
    L[i:i + len(sig)] += sig * gain * (1 - max(0, pan))
    R[i:i + len(sig)] += sig * gain * (1 + min(0, pan))


n_bars = int(np.ceil(total / BAR))
for bar in range(n_bars):
    t0 = bar * BAR
    ci = bar % 4
    chord = CHORDS[ci]
    # sections (in bars): 0-1 intro, 2-3 build, 4.. chorus, last 2 outro
    intro = bar < 2
    build = 2 <= bar < 4
    chorus = 4 <= bar < n_bars - 2
    outro = bar >= n_bars - 2

    # piano arpeggio in eighth notes
    arp = chord + [chord[0] + 12, chord[1] + 12]
    pattern = [0, 1, 2, 3, 4, 3, 2, 1]
    for i, p in enumerate(pattern):
        add(piano(midi(arp[p] + 12), BEAT * 1.2, 0.9 if i % 2 == 0 else 0.6),
            t0 + i * BEAT / 2, 0.34, pan=(-0.3 if i % 2 else 0.3))

    if not intro:
        add(pad([midi(n) for n in chord], BAR + 0.6), t0, 0.22 if build else 0.3)
        add(bass(midi(BASS[ci]), BAR), t0, 0.35)
    if chorus:
        for b, note in enumerate(MELODY[ci]):
            add(piano(midi(note), BEAT * 1.5, 1.0), t0 + b * BEAT, 0.4)
    if build or chorus:
        for b in range(4):
            add(kick(), t0 + b * BEAT, 0.55 if chorus else 0.35)
            for h in range(2):
                add(hat(), t0 + b * BEAT + h * BEAT / 2, 0.05 if chorus else 0.03, pan=0.4)
        if chorus:
            add(snare(), t0 + BEAT, 0.25)
            add(snare(), t0 + 3 * BEAT, 0.25)
    if bar == 3:
        add(riser(BAR), t0, 0.12)
    if outro:
        add(pad([midi(n) for n in chord], BAR + 1.5), t0, 0.3)

mix = np.stack([L, R], axis=1)[:N]
# simple reverb-ish smear: feedback delays
for d, g in ((0.031, 0.25), (0.047, 0.2), (0.089, 0.15), (0.137, 0.1)):
    k = int(d * SR)
    mix[k:] += mix[:-k] * g
# master fade in/out + normalize
fade_in, fade_out = int(0.5 * SR), int(3.0 * SR)
mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
mix = np.tanh(mix / np.abs(mix).max() * 1.4) * 0.9

from scipy.io import wavfile
wavfile.write(out_path, SR, (mix * 32767).astype(np.int16))
print(f"wrote {out_path} ({total:.1f}s, {BPM} BPM)")
