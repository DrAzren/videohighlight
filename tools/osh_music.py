"""Synthesize an original, royalty-free feel-good indie-pop / electronic track for a 30 s reel.

120 BPM in D major, I-V-vi-IV (D A Bm G), one chord per bar. Bars start on odd seconds
(downbeat offset 1.0 s) so the reel's section changes at 3, 17 and 25 s land on bar lines;
0-1 s is a two-beat pickup that opens on an impact.

  0-1   pickup     impact, kick, chord stab on V
  1-3   hook       full groove: four-on-the-floor, claps, supersaw chords, pluck hook
  3-9   atmosphere lighter: filtered pad, 16th pluck arp, off-beat hats; snare build 8-9
  9-17  best       everything + lead hook, claps, shaker
  17-25 montage    + bells an octave up; 21-25 build (filter opens, snare roll, riser)
  25-27 peak       crash, half-time drums, lead resolves
  27-30 resolve    pad + pluck, final D chord rings out, fade to silence at 30 s

Usage: python3 osh_music.py OUT.wav [STEMS_DIR]
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
BPM = 120
BEAT = 60 / BPM
DUR = 30.0
OFF = 1.0                       # first downbeat
N = int(DUR * SR)
rng = np.random.default_rng(2026)

CHORDS = {"D": [50, 54, 57], "A": [45, 49, 52], "Bm": [47, 50, 54], "G": [43, 47, 50]}
PROG = ["D", "A", "Bm", "G"]
# lead hook: eighth notes per chord (None = rest)
HOOK = {
    "D": [78, 81, 83, 81, 78, None, 76, 74],
    "A": [76, 81, 76, 73, 76, None, 78, 76],
    "Bm": [74, 78, 83, 81, 78, None, 76, 78],
    "G": [79, 78, 76, 74, 76, None, 74, 69],
}


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 - 200) / (SR / 2), "low", output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), "high", output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos"), x)


def saw(f, n, phase=0.0):
    t = np.arange(n) / SR
    return 2 * ((f * t + phase) % 1.0) - 1


def env(n, a=0.005, d=0.1, s=0.7, r=0.08):
    e = np.full(n, s, dtype=float)
    an, dn, rn = int(a * SR), int(d * SR), int(r * SR)
    an = min(an, n)
    e[:an] = np.linspace(0, 1, an)
    dn = min(dn, n - an)
    e[an:an + dn] = np.linspace(1, s, dn)
    rn = min(rn, n)
    e[n - rn:] *= np.linspace(1, 0, rn)
    return e


def place(buf, sig, t, gain=1.0):
    i = int(round(t * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    s0 = max(0, -i)
    j = min(len(buf), i + len(sig))
    buf[max(i, 0):j] += gain * sig[s0:s0 + j - max(i, 0)]


def bar_chord(t):
    """Chord name sounding at time t (pickup bar plays V)."""
    if t < OFF:
        return "A"
    k = int((t - OFF) // (4 * BEAT))
    if t >= 29.0:
        return "D"
    if 25.0 <= t < 27.0:
        return "D"
    if 27.0 <= t < 29.0:
        return "G" if t < 28.0 else "A"
    return PROG[k % 4]


def section(t):
    if t < 1: return "pickup"
    if t < 3: return "hook"
    if t < 9: return "atmos"
    if t < 17: return "best"
    if t < 25: return "montage"
    if t < 27: return "peak"
    return "resolve"


# ---------------------------------------------------------------- instruments
def kick(vel=1.0):
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = 46 + 110 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    click = hp(rng.standard_normal(n), 2500) * np.exp(-t * 300) * 0.25
    return vel * np.tanh(1.6 * (body + click))


def clap(vel=1.0):
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    noise = bp(rng.standard_normal(n), 900, 3200)
    e = np.zeros(n)
    for k, dt in enumerate([0, 0.011, 0.022]):
        i = int(dt * SR)
        e[i:] += np.exp(-(t[: n - i]) * 140) * (0.8 if k < 2 else 1.0)
    e += np.exp(-np.maximum(t - 0.022, 0) * 18) * 0.35 * (t > 0.022)
    return vel * 0.6 * noise * e


def snare(vel=1.0):
    n = int(0.28 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 188 * t) * np.exp(-t * 28)
    noise = bp(rng.standard_normal(n), 1200, 9000) * np.exp(-t * 22)
    return vel * 0.55 * (0.5 * tone + noise)


def hat(open_=False, vel=1.0):
    n = int((0.22 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    s = hp(rng.standard_normal(n), 8000, 4)
    return vel * 0.22 * s * np.exp(-t * (14 if open_ else 90))


def shaker(vel=1.0):
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    s = bp(rng.standard_normal(n), 5000, 12000)
    e = np.sin(np.pi * np.clip(t / 0.09, 0, 1)) ** 2
    return vel * 0.12 * s * e


def crash(vel=1.0, length=2.2):
    n = int(length * SR)
    t = np.arange(n) / SR
    s = hp(rng.standard_normal(n), 4500, 2) + 0.3 * bp(rng.standard_normal(n), 2500, 6000)
    return vel * 0.28 * s * np.exp(-t * 2.2)


def supersaw(notes, dur, cutoff=3500, voices=5, detune=0.12):
    n = int(dur * SR)
    out = np.zeros(n)
    for m in notes:
        for v in range(voices):
            cents = (v - (voices - 1) / 2) * detune * 100 / ((voices - 1) / 2)
            out += saw(hz(m) * 2 ** (cents / 1200), n, rng.random())
    out = lp(out / (len(notes) * voices), cutoff)
    return out * env(n, 0.02, 0.2, 0.85, 0.12)


def pluck(m, dur=0.25, bright=4500, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = 0.6 * saw(hz(m), n) + 0.4 * np.sign(np.sin(2 * np.pi * hz(m) * t)) * 0.5
    x = lp(x, bright) * np.exp(-t * 9)
    x += 0.35 * np.sin(2 * np.pi * hz(m) * t) * np.exp(-t * 6)
    return vel * x * env(n, 0.002, 0.05, 1.0, 0.03)


def bell(m, dur=1.2, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t * 3)
         + 0.5 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 5)
         + 0.25 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 8))
    return vel * 0.35 * x * env(n, 0.002, 0.05, 1.0, 0.1)


def bass_note(m, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * hz(m) * t) + 0.35 * lp(saw(hz(m), n), 900)
    return vel * 0.75 * np.tanh(1.3 * x) * env(n, 0.004, 0.08, 0.8, 0.05)


def riser(dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    seg = int(0.05 * SR)
    for i in range(0, n, seg):           # sweeping band-pass, block-wise
        fc = 400 * (12000 / 400) ** (i / n)
        out[i:i + seg] = bp(noise[i:i + seg + 2000], fc * 0.7, min(fc * 1.4, 20000))[: min(seg, n - i)]
    tone = saw(1, n) * 0
    f = 110 * 2 ** (3 * t / dur)
    tone = lp(2 * ((np.cumsum(f) / SR) % 1) - 1, 3000)
    return (0.5 * out + 0.12 * tone) * (t / dur) ** 2


# ---------------------------------------------------------------- arrange
drums, bass, chords, lead, arp, fx = (np.zeros(N) for _ in range(6))
kicks = []

nb = int(DUR / BEAT)
for b in range(nb):
    t = b * BEAT
    sec = section(t)
    in_bar = int(round((t - OFF) / BEAT)) % 4     # 0 = downbeat
    # kick
    if sec in ("pickup", "hook", "atmos", "best", "montage"):
        v = 0.8 if sec == "atmos" else 1.0
        place(drums, kick(v), t); kicks.append(t)
    elif sec == "peak" and in_bar in (0,):
        place(drums, kick(1.0), t); kicks.append(t)
    elif sec == "peak" and in_bar == 2:
        place(drums, snare(1.0), t); place(drums, clap(0.8), t)
    elif sec == "resolve" and t < 29 and in_bar == 0:
        place(drums, kick(0.6), t); kicks.append(t)
    # backbeat claps
    if sec in ("hook", "best", "montage") and in_bar in (1, 3):
        place(drums, clap(1.0), t)
    if sec == "atmos" and t >= 7.0 and in_bar in (1, 3):
        place(drums, clap(0.55), t)
    # hats
    if sec in ("hook", "atmos", "best", "montage"):
        place(drums, hat(True, 0.9 if sec != "atmos" else 0.7), t + BEAT / 2)
        if sec in ("best", "montage"):
            for k in range(4):
                place(drums, shaker(0.9 if k % 2 else 0.6), t + k * BEAT / 4)
        else:
            place(drums, hat(False, 0.6), t + BEAT / 4)
            place(drums, hat(False, 0.5), t + 3 * BEAT / 4)

# snare builds: 8-9 (8ths -> 16ths), 23-25 (16ths, rising)
for k in range(8):
    place(drums, snare(0.35 + 0.08 * k), 8.0 + k * BEAT / 4)
for k in range(16):
    place(drums, snare(0.25 + 0.045 * k), 23.0 + k * BEAT / 8 * 2)
for k in range(8):
    place(drums, snare(0.6 + 0.05 * k), 24.0 + k * BEAT / 4 * 1.0 / 1.0 * 0.5 + 0.0)
# pickup fill
place(drums, snare(0.7), 0.5); place(drums, snare(0.85), 0.75)

# crashes
for t, v in [(0.0, 1.0), (1.0, 0.7), (9.0, 0.9), (17.0, 0.8), (25.0, 1.1)]:
    place(fx, crash(v, 2.6), t)

# bass + chords per bar (and pickup)
bar_starts = [0.0] + [OFF + 2 * k for k in range(15)]
for bs in bar_starts:
    be = 1.0 if bs == 0.0 else min(bs + 2.0, DUR)
    name = bar_chord(bs + 0.01)
    root = CHORDS[name][0] - 12
    sec = section(bs + 0.01)
    if sec == "resolve" and bs >= 29:
        place(bass, bass_note(root, 1.0, 0.8) * np.exp(-np.arange(int(1.0 * SR)) / SR * 1.5), bs)
    elif sec == "peak":
        place(bass, bass_note(root, 1.9, 1.0), bs)
    else:
        step = BEAT / 2
        for k in range(int(round((be - bs) / step))):
            t = bs + k * step
            if sec == "atmos" and k % 2:
                continue
            octave = 12 if (k % 4 == 3 and sec in ("best", "montage")) else 0
            place(bass, bass_note(root + octave, step * 0.9, 0.9), t)
    # chords
    notes = [m + 12 for m in CHORDS[name]] + [CHORDS[name][0] + 24]
    if sec in ("pickup",):
        place(chords, supersaw(notes, 0.45, 5000), bs + 0.5, 0.9)
    elif sec == "atmos":
        place(chords, supersaw(notes, be - bs, 900 + 250 * (bs - 3)), bs, 0.8)
    elif sec in ("hook", "best"):
        place(chords, supersaw(notes, be - bs, 4200), bs, 0.85)
    elif sec == "montage":
        cut = 4200 if bs < 21 else 4200 + 1600 * (bs - 21)
        place(chords, supersaw(notes, be - bs, cut), bs, 0.85)
    elif sec == "peak":
        place(chords, supersaw(notes + [notes[1] + 12], 2.0, 6500, voices=7), bs, 1.0)
    else:
        length = 2.0 if bs < 29 else 1.0
        place(chords, supersaw(notes, length, 2200), bs, 0.8)

# 16th arp in atmosphere + resolve
for b16 in range(int(DUR / (BEAT / 4))):
    t = b16 * BEAT / 4
    sec = section(t)
    if sec in ("atmos",) or (sec == "resolve" and t < 29):
        ch = CHORDS[bar_chord(t)]
        pat = [ch[0] + 24, ch[1] + 24, ch[2] + 24, ch[1] + 36]
        place(arp, pluck(pat[b16 % 4], 0.18, 3000 + (t - 3) * 300, 0.55), t)

# lead hook (8ths) in hook, best, montage, peak
for k in range(int(DUR / (BEAT / 2))):
    t = k * BEAT / 2
    sec = section(t)
    if sec not in ("hook", "best", "montage", "peak"):
        continue
    if sec == "peak" and t >= 26.5:
        continue
    name = bar_chord(t)
    idx = int(round((t - OFF) / (BEAT / 2))) % 8
    m = HOOK[name][idx]
    if m is None:
        continue
    if sec == "peak":
        m = [78, 81, 83, 86, 85, None, 81, None][idx] or m
    place(lead, pluck(m, 0.32, 5200, 0.8), t)
    if sec == "montage" and idx % 2 == 0:
        place(lead, bell(m + 12, 0.9, 0.5), t)
# final melody note + bell on the tonic chord
place(lead, pluck(74, 1.0, 4000, 0.7), 29.0)
place(lead, bell(86, 1.0, 0.6), 29.0)

# risers
place(fx, riser(1.0), 8.0, 0.8)
place(fx, riser(4.0), 21.0, 1.0)

# ---------------------------------------------------------------- mix
t = np.arange(N) / SR
duck = np.ones(N)                       # sidechain pump from every kick
for kt in kicks:
    i = int(kt * SR)
    seg = np.arange(min(int(0.3 * SR), N - i)) / SR
    duck[i:i + len(seg)] = np.minimum(duck[i:i + len(seg)], 1 - 0.55 * np.exp(-seg / 0.09))

ir_n = int(1.8 * SR)
ir_t = np.arange(ir_n) / SR
ir = lp(rng.standard_normal(ir_n), 6000) * np.exp(-ir_t * 3.2)
ir /= np.sqrt((ir ** 2).sum())


def verb(x, amt):
    return x + amt * fftconvolve(x, ir)[:N]


stems = {
    "drums": drums,
    "bass": lp(bass, 4000) * duck,
    "chords": verb(chords * duck, 0.35),
    "arp": verb(arp, 0.3),
    "lead": verb(lead, 0.28),
    "fx": verb(fx, 0.15),
}
gains = {"drums": 0.9, "bass": 0.7, "chords": 0.42, "arp": 0.35, "lead": 0.45, "fx": 0.5}
mono = sum(gains[k] * v for k, v in stems.items())

# light stereo: chords / arp / lead widened with short opposite delays
wide = gains["chords"] * stems["chords"] + gains["arp"] * stems["arp"] + 0.5 * gains["lead"] * stems["lead"]
d1, d2 = int(0.011 * SR), int(0.017 * SR)
L = mono + 0.35 * np.concatenate([np.zeros(d1), wide[:-d1]])
R = mono + 0.35 * np.concatenate([np.zeros(d2), wide[:-d2]])
mix = np.stack([L, R], 1)

# final fade: 29.0 -> 30.0
fade = np.ones(N)
fs = int(29.2 * SR)
fade[fs:] = np.linspace(1, 0, N - fs) ** 1.5
mix *= fade[:, None]

mix = np.tanh(1.2 * mix / np.max(np.abs(mix))) / np.tanh(1.2)
mix *= 0.89 / np.max(np.abs(mix))
sf.write(sys.argv[1], mix.astype(np.float32), SR, subtype="PCM_24")
if len(sys.argv) > 2:
    d = Path(sys.argv[2]); d.mkdir(parents=True, exist_ok=True)
    for k, v in stems.items():
        sf.write(d / f"{k}.wav", (gains[k] * v * fade).astype(np.float32), SR, subtype="PCM_24")
print(f"wrote {sys.argv[1]} ({DUR}s, {BPM} BPM, kicks={len(kicks)})")
