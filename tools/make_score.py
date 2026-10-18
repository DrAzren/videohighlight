"""Generate an original, royalty-free cinematic orchestral score timed to the
Forum Intelektual Diraja highlight film (75.5 s).

Arc (seconds):
  0.0 - 5.5   hook      : low D pedal, high string harmonics, sparse piano, soft swell
  5.5 - 13.0  journey   : D A G    warm piano ostinato, pizzicato pulse, light ticks
  13.0 - 18.0 rehearsal : Bm G     hushed harmonics, piano motif, riser into the impact
  18.0        IMPACT    : timpani + low boom + full string/horn chord
  18.0 - 23.0 titles    : Bm - G   strings + soft piano arpeggio
  23.0 - 30.5 occasion  : Bm G D   spiccato ostinato, timpani pulse, horns
  30.5 - 35.5 main      : G D      + choir, horn theme
  35.5 - 40.5 speech    : A Bm     sustained bed only (ducked in the final mix)
  40.5 - 43.0 rise      : A(sus)   held back until the quote ends, then roll + riser
  43.0 - 55.5 payoff    : D A Bm G A  full theme, choir, crescendo
  55.5 - 65.5 personal  : D Bm G A warm strings, piano melody, gentle pulse
  65.5 - 75.5 closing   : D G D    piano + soft strings, final resolution

96 BPM, bars of 2.5 s anchored at 5.5 s, D major.
Usage: python3 make_score.py OUT.wav
"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
BEAT = 0.625
BAR = 4 * BEAT
END = 75.5
N = int((END + 0.5) * SR)
rng = np.random.default_rng(11)
out_path = sys.argv[1] if len(sys.argv) > 1 else "score.wav"


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def lp(x, fc, order=2):
    return sosfilt(butter(order, min(fc, SR / 2 - 200) / (SR / 2), "low", output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), "high", output="sos"), x)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), hi / (SR / 2)], "band", output="sos"), x)


def env(n, a, r, curve=1.0):
    e = np.ones(n)
    a_n, r_n = max(1, min(n, int(a * SR))), max(1, min(n, int(r * SR)))
    e[:a_n] = np.linspace(0, 1, a_n) ** curve
    e[-r_n:] *= np.linspace(1, 0, r_n) ** curve
    return e


def saw(f, n, vib=None):
    ph = np.cumsum(np.full(n, f) * (vib if vib is not None else 1)) / SR + rng.random()
    return 2 * (ph % 1) - 1


# ---- buses -----------------------------------------------------------------------
BUSES = {k: np.zeros((N, 2)) for k in ("strings", "brass", "choir", "piano", "perc", "fx")}


def add(bus, sig, t, g=1.0, pan=0.0):
    i = int(t * SR)
    if i >= N or g == 0:
        return
    sig = sig[: N - i]
    if sig.ndim == 1:
        l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
        BUSES[bus][i:i + len(sig), 0] += sig * g * l * 1.414
        BUSES[bus][i:i + len(sig), 1] += sig * g * r * 1.414
    else:
        BUSES[bus][i:i + len(sig)] += sig * g


# ---- instruments --------------------------------------------------------------------
def strings(notes, dur, att=0.6, rel=0.9, bright=2600, voices=6):
    """Ensemble strings: detuned saws with delayed vibrato, stereo-spread."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for m in notes:
        f = hz(m)
        for v in range(voices):
            rate = 4.6 + rng.random() * 1.4
            depth = 0.0022 * np.minimum(1, t / 0.8)
            vib = 1 + depth * np.sin(2 * np.pi * rate * t + rng.random() * 6.28)
            s = saw(f * 2 ** (rng.normal(0, 0.07) / 12), n, vib)
            p = (v / (voices - 1)) * 1.4 - 0.7
            out[:, 0] += s * (1 - p) * 0.5
            out[:, 1] += s * (1 + p) * 0.5
    out /= len(notes) * voices
    fc = bright * (1 + 0.15 * (np.mean(notes) - 60) / 12)
    for c in range(2):
        x = lp(lp(out[:, c], fc), fc * 1.6)
        x += 0.35 * bp(x, 2200, 4200)          # violin presence
        out[:, c] = hp(x, 55)
    e = env(n, att, rel, 1.6)
    e[int(dur * SR):] *= 1  # release already shaped
    return out * e[:, None] * 2.2


def spiccato(m, dur=0.22):
    n = int((dur + 0.15) * SR)
    t = np.arange(n) / SR
    s = sum(saw(hz(m) * 2 ** (d / 1200), n) for d in (-9, 0, 8)) / 3
    s = lp(s, 2400) * np.exp(-t * 14) * env(n, 0.006, 0.08)
    return s * 1.6


def horn(notes, dur, att=0.35, rel=0.8):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        vib = 1 + 0.0018 * np.sin(2 * np.pi * 4.8 * t) * np.minimum(1, t / 0.6)
        ph = 2 * np.pi * np.cumsum(hz(m) * vib) / SR
        s += sum(np.sin(k * ph) * (0.75 ** k) for k in range(1, 10))
    s /= len(notes)
    # brass "swell": brightness follows the amplitude envelope
    e = env(n, att, rel, 1.4)
    dark, bright = lp(s, 700), lp(s, 2200)
    return (dark * (1 - e) * 0.4 + bright * e) * e * 0.9


def choir(notes, dur, att=0.9, rel=1.2):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for m in notes:
        for d in (-0.12, 0.0, 0.1):
            vib = 1 + 0.003 * np.sin(2 * np.pi * (5.0 + d * 3) * t + rng.random() * 6)
            ph = 2 * np.pi * np.cumsum(hz(m) * 2 ** (d / 12) * vib) / SR
            s += np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.2 * np.sin(3 * ph) + 0.12 * np.sin(4 * ph)
    s = 0.9 * bp(s, 300, 900) + 0.6 * bp(s, 1000, 1400) + 0.25 * bp(s, 2400, 3200) + 0.4 * lp(s, 400)
    return s / (len(notes) * 3) * env(n, att, rel, 1.5) * 1.6


def piano(m, dur, vel=0.7):
    f = hz(m)
    n = int((dur + 2.5) * SR)
    t = np.arange(n) / SR
    B = 0.00035
    s = np.zeros(n)
    for k in range(1, 14):
        fk = f * k * np.sqrt(1 + B * k * k)
        if fk > SR / 2.2:
            break
        amp = (1 / k ** 1.15) * (vel ** (0.5 + 0.12 * k))
        dec = 0.55 + 0.32 * k + 0.002 * f
        for det in (-0.25, 0.25):                       # two-string unison beat
            s += amp * np.sin(2 * np.pi * (fk + det) * t + rng.random()) * np.exp(-t * dec)
    s *= 0.5
    ham = lp(rng.standard_normal(n), 3000) * np.exp(-t * 90) * 0.08 * vel
    damp = np.ones(n)
    off = int(dur * SR)
    if off < n:
        damp[off:] = np.exp(-np.arange(n - off) / SR * 7)
    return (s + ham) * env(n, 0.002, 0.05) * damp * 0.55


def timpani(m, vel=0.8, roll=0.0):
    n = int(3.0 * SR)
    t = np.arange(n) / SR
    f = hz(m) * (1 + 0.025 * np.exp(-t * 25))
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = sum(a * np.sin(r * ph) * np.exp(-t * d) for r, a, d in
               ((1, 1.0, 1.6), (1.5, 0.45, 2.6), (1.98, 0.3, 3.2), (2.44, 0.18, 4.0), (2.9, 0.1, 5.0)))
    stick = lp(rng.standard_normal(n), 900) * np.exp(-t * 40) * 0.6
    return np.tanh(1.3 * (body + stick)) * vel


def boom(dur=4.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 32 + 55 * np.exp(-t * 4)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.1)
    s += lp(rng.standard_normal(n), 400) * np.exp(-t * 6) * 0.6
    return np.tanh(2.0 * s) * 0.9


def cymbal(dur=4.0, swell=False):
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = hp(rng.standard_normal(n), 3500)
    ring = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) for f in (3170, 4410, 5530, 6870, 8120)) * 0.08
    s = nz * 0.6 + ring
    e = (t / dur) ** 3 if swell else np.exp(-t * 1.3) * env(n, 0.002, 0.3)
    return s * e * 0.5


def riser(dur):
    n = int(dur * SR)
    x = np.linspace(0, 1, n)
    nz = rng.standard_normal(n)
    out = np.zeros(n)
    seg = n // 16
    for i in range(16):
        a, b = i * seg, min(n, (i + 1) * seg + seg)
        lo = 300 + 5000 * (i / 16) ** 1.5
        out[a:b] += bp(nz[a:b], lo, lo * 2.2) * np.hanning(b - a)
    return out * x ** 2.2 * 0.7


def drone(m, dur, att=1.5, rel=1.5):
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = sum(saw(hz(m) * 2 ** (d / 1200), n) for d in (-6, 0, 7)) / 3
    s = lp(s, 380) + 0.6 * np.sin(2 * np.pi * hz(m) * t)
    return s * env(n, att, rel, 1.5) * (1 + 0.15 * np.sin(2 * np.pi * 0.2 * t))


def harmonics(m, dur, att=1.2, rel=1.5):
    """Airy high violin harmonics with tremolo shimmer."""
    n = int((dur + rel) * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * hz(m) * t) + 0.3 * np.sin(4 * np.pi * hz(m) * t)
    trem = 0.75 + 0.25 * np.sin(2 * np.pi * 7.5 * t)
    return s * trem * env(n, att, rel, 2.0) * 0.5


# ---- harmony ----------------------------------------------------------------------------
CH = {   # strings voicing, horn voicing, bass note
    "D":  ([50, 57, 62, 66, 69, 74], [62, 66, 69], 38),
    "Bm": ([47, 54, 62, 66, 71, 74], [62, 66, 71], 35),
    "G":  ([43, 55, 62, 67, 71, 74], [59, 62, 67], 31),
    "A":  ([45, 52, 61, 64, 69, 73], [61, 64, 69], 33),
    "As": ([45, 52, 62, 64, 69, 74], [62, 64, 69], 33),
}
ARP = {"D": [62, 66, 69, 74], "Bm": [59, 62, 66, 71], "G": [59, 62, 67, 71], "A": [61, 64, 69, 73],
       "As": [62, 64, 69, 74]}

# ---- 0 - 5.5 hook ----------------------------------------------------------------
add("strings", drone(26, 5.8, att=2.0), 0.0, 0.3)
add("strings", drone(38, 5.8, att=2.5), 0.0, 0.14)
add("strings", np.stack([harmonics(81, 5.3), harmonics(86, 5.3)], 1) * 0.5, 0.4, 0.22)
for tt, m in ((0.9, 69), (2.3, 74), (4.45, 78), (5.0, 76)):   # clear of "memulakan bicara" (~3.3-4.35 s)
    add("piano", piano(m, 1.6, 0.45), tt, 0.26, 0.2)
add("fx", cymbal(1.2, swell=True), 4.3, 0.25)
add("choir", choir([62, 69], 4.5, att=2.5, rel=0.8), 1.0, 0.18)


def pizz(m):
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    s = sum(np.sin(2 * np.pi * hz(m) * k * t) * 0.6 ** k for k in range(1, 6))
    return s * np.exp(-t * 9) * env(n, 0.003, 0.1)


def tick():
    n = int(0.08 * SR)
    return hp(rng.standard_normal(n), 6000) * np.exp(-np.arange(n) / SR * 70)


# ---- 5.5 - 13.0 journey -----------------------------------------------------------------
TJ = 5.5
for i, name in enumerate(("D", "A", "G")):
    sv, hv, bass = CH[name]
    t = TJ + i * BAR
    add("strings", strings(sv[1:5], BAR, att=0.5, rel=0.6, bright=1900), t, 0.38 + 0.06 * i)
    add("strings", drone(bass, BAR, att=0.2, rel=0.4), t, 0.3)
    for k in range(8):                                  # travelling piano ostinato, 8ths
        m = ARP[name][[0, 2, 1, 3, 0, 2, 1, 3][k]] + 12
        add("piano", piano(m, BEAT * 0.8, 0.4 + 0.06 * (k % 4 == 0)), t + k * BEAT / 2, 0.24,
            0.25 if k % 2 else -0.2)
    for b in range(4):
        add("strings", pizz(bass + 12), t + b * BEAT, 0.3, -0.3)
        add("perc", tick(), t + b * BEAT + BEAT / 2, 0.12 + 0.03 * i, 0.4)

# ---- 13.0 - 18.0 rehearsal ------------------------------------------------------------------
TR = 13.0
for i, name in enumerate(("Bm", "G")):
    sv, hv, bass = CH[name]
    t = TR + i * BAR
    add("strings", strings(sv[1:4], BAR, att=0.8, rel=0.6, bright=1400), t, 0.32)
    add("strings", drone(bass, BAR, att=0.4, rel=0.4), t, 0.28)
    add("strings", np.stack([harmonics(hv[2] + 12, BAR), harmonics(hv[1] + 24, BAR)], 1) * 0.5, t, 0.16)
    for k, m in enumerate((ARP[name][3] + 12, ARP[name][1] + 12, ARP[name][2] + 12)):
        add("piano", piano(m, BEAT * 1.6, 0.42), t + k * BEAT * 1.33, 0.26, 0.2)
    for b in range(4):
        add("perc", tick(), t + b * BEAT, 0.1 + 0.04 * i, -0.3)
add("fx", riser(BAR), TR + BAR, 0.5)
add("fx", cymbal(BAR, swell=True), TR + BAR, 0.5)

# ---- 18.0 impact + titles ------------------------------------------------------
T0 = 18.0
add("perc", boom(), T0, 0.9)
add("perc", timpani(35, 1.0), T0, 0.8)
add("perc", timpani(47, 0.7), T0 + 0.01, 0.45)
add("fx", cymbal(4.5), T0, 0.45)
for i, (name, bars) in enumerate((("Bm", 1), ("G", 1))):
    sv, hv, bass = CH[name]
    t = T0 + i * BAR
    add("strings", strings(sv, BAR * bars, att=0.08 if i == 0 else 0.5, rel=1.0), t, 0.75)
    add("brass", horn(hv, BAR * bars, att=0.12 if i == 0 else 0.5), t, 0.35, -0.2)
    add("strings", drone(bass, BAR * bars, att=0.05, rel=0.8), t, 0.35)
    for k in range(8):                                  # gentle piano arpeggio, 8ths
        m = ARP[name][[0, 1, 2, 3, 2, 1, 2, 3][k]] + 12
        add("piano", piano(m, BEAT * 0.9, 0.38 + 0.04 * (k % 4 == 0)), t + k * BEAT / 2, 0.22,
            0.3 if k % 2 else -0.1)

# ---- 10.5 - 20.5 occasion ---------------------------------------------------
T1 = 23.0
for i, name in enumerate(("Bm", "G", "D")):
    sv, hv, bass = CH[name]
    t = T1 + i * BAR
    lvl = 0.55 + 0.08 * i
    add("strings", strings(sv[:4], BAR, att=0.4, rel=0.6), t, lvl)
    add("brass", horn(hv, BAR, att=0.6, rel=0.5), t, 0.18 + 0.05 * i, 0.2)
    add("strings", drone(bass, BAR, att=0.05, rel=0.4), t, 0.4)
    root = sv[0] + 12
    for k in range(8):                                  # spiccato ostinato
        m = root + [0, 12, 7, 12, 0, 12, 7, 19][k]
        add("strings", spiccato(m), t + k * BEAT / 2, (0.13 + 0.03 * i) * (1.2 if k % 2 == 0 else 0.8),
            -0.4 if k % 2 else 0.4)
    for b in (0, 2):
        add("perc", timpani(bass + 12 if bass < 36 else bass, 0.5 + 0.08 * i), t + b * BEAT, 0.42)
    if i >= 2:
        add("perc", timpani(bass + 12 if bass < 36 else bass, 0.35), t + 3.5 * BEAT, 0.3)
add("fx", riser(BAR), T1 + 2 * BAR, 0.4)
add("fx", cymbal(BAR, swell=True), T1 + 2 * BAR, 0.4)

# ---- 20.5 - 25.5 main ---------------------------------------------------------------
T2 = 30.5
add("perc", timpani(31 + 12, 0.85), T2, 0.6)
add("fx", cymbal(3.5), T2, 0.3)
HORN_THEME = [  # (bar, beat, beats, midi)
    (0, 0, 2, 74), (0, 2, 1, 71), (0, 3, 1, 74),
    (1, 0, 3, 69), (1, 3, 1, 66),
]
for i, name in enumerate(("G", "D")):
    sv, hv, bass = CH[name]
    t = T2 + i * BAR
    add("strings", strings(sv, BAR, att=0.25, rel=0.7), t, 0.6)
    add("choir", choir(hv, BAR, att=0.6, rel=0.8), t, 0.32)
    add("strings", drone(bass, BAR, att=0.05, rel=0.5), t, 0.45)
    root = sv[0] + 12
    for k in range(8):
        m = root + [0, 12, 7, 12, 0, 12, 7, 19][k]
        add("strings", spiccato(m), t + k * BEAT / 2, 0.2 * (1.2 if k % 2 == 0 else 0.8),
            -0.4 if k % 2 else 0.4)
    for b in range(4):
        add("perc", timpani(bass + 12 if bass < 36 else bass, 0.55 if b % 2 == 0 else 0.35),
            t + b * BEAT, 0.4)
for bar, beat, beats, m in HORN_THEME:
    add("brass", horn([m - 12, m], beats * BEAT * 0.98, att=0.12, rel=0.4),
        T2 + bar * BAR + beat * BEAT, 0.42, -0.15)

# ---- 25.5 - 33.0 speech bed (sustained, no percussion) -----------------------------
T3 = 35.5
for i, name in enumerate(("A", "Bm")):
    sv, hv, bass = CH[name]
    t = T3 + i * BAR
    add("strings", strings(sv[1:5], BAR, att=0.9, rel=1.0, bright=1600), t, 0.55)
    add("strings", drone(bass, BAR, att=0.6, rel=0.8), t, 0.3)
    for k, m in enumerate(ARP[name][:3]):
        add("piano", piano(m, BEAT * 3, 0.32), t + k * BEAT * 1.33, 0.2, 0.25)

# ---- 33.0 - 35.5 rise -----------------------------------------------------------------
T4 = 40.5                                               # the quote runs to ~41.3 s
sv, hv, bass = CH["As"]
add("strings", strings(sv, BAR * 0.5, att=1.0, rel=0.1), T4, 0.5)
sv, hv, bass = CH["A"]
add("strings", strings(sv, BAR * 0.5, att=0.2, rel=0.3), T4 + BAR * 0.5, 0.75)
add("brass", horn(hv, BAR * 0.6, att=1.0, rel=0.2), T4 + BAR * 0.4, 0.35)
for k in range(16):                                     # timpani roll crescendo, last 1.5 s
    add("perc", timpani(45, 0.2 + 0.04 * k), T4 + 1.0 + k * 1.5 / 16, 0.3)
add("fx", riser(1.6), T4 + 0.9, 0.6)
add("fx", cymbal(1.6, swell=True), T4 + 0.9, 0.55)

# ---- 35.5 - 48.0 payoff ----------------------------------------------------------------
T5 = 43.0
PROG = ("D", "A", "Bm", "G", "A")
THEME = [  # (bar, beat, beats, midi) - violins, doubled by horn an octave below
    (0, 0, 1, 69), (0, 1, 1, 74), (0, 2, 2, 78),
    (1, 0, 1.5, 76), (1, 1.5, 0.5, 74), (1, 2, 1, 73), (1, 3, 1, 69),
    (2, 0, 1, 71), (2, 1, 1, 74), (2, 2, 1, 78), (2, 3, 1, 81),
    (3, 0, 2, 83), (3, 2, 1, 81), (3, 3, 1, 79),
    (4, 0, 1, 78), (4, 1, 1, 76), (4, 2, 2, 76),
]
add("perc", boom(3.0), T5, 0.6)
add("perc", timpani(38, 1.0), T5, 0.7)
add("fx", cymbal(4.0), T5, 0.42)
for i, name in enumerate(PROG):
    sv, hv, bass = CH[name]
    t = T5 + i * BAR
    lvl = 0.72 + 0.1 * i
    add("strings", strings(sv, BAR, att=0.12, rel=0.6, bright=3000), t, lvl)
    add("brass", horn(hv, BAR, att=0.2, rel=0.5), t, 0.28 + 0.06 * i, 0.15)
    add("choir", choir(hv + [hv[0] + 12], BAR, att=0.4, rel=0.8), t, 0.3 + 0.07 * i)
    add("strings", drone(bass, BAR, att=0.03, rel=0.4), t, 0.5)
    root = sv[0] + 12
    for k in range(8):
        m = root + [0, 12, 7, 12, 0, 12, 7, 19][k]
        add("strings", spiccato(m), t + k * BEAT / 2, 0.22 * (1.2 if k % 2 == 0 else 0.8),
            -0.4 if k % 2 else 0.4)
    for b in range(4):
        add("perc", timpani(bass + 12 if bass < 36 else bass, 0.75 if b == 0 else 0.45),
            t + b * BEAT, 0.42 + 0.03 * i)
    if i == 3:
        add("fx", cymbal(3.0), t, 0.3)
    if i == 4:                                          # roll into the resolution
        for k in range(16):
            add("perc", timpani(45, 0.2 + 0.035 * k), t + 2 * BEAT + k * BEAT / 8, 0.3)
        add("fx", cymbal(BAR, swell=True), t, 0.45)
for bar, beat, beats, m in THEME:
    d = beats * BEAT
    t = T5 + bar * BAR + beat * BEAT
    add("strings", strings([m, m + 12], d * 0.98, att=0.05, rel=0.35, bright=4200, voices=5), t, 0.5)
    add("brass", horn([m - 12], d * 0.98, att=0.08, rel=0.3), t, 0.3, -0.25)

# ---- 55.5 - 65.5 personal moments -----------------------------------------------------------
TP = 55.5
MEL_P = [  # (bar, beat, beats, midi) - gentle piano melody
    (0, 0, 2, 78), (0, 2, 1, 76), (0, 3, 1, 74),
    (1, 0, 3, 74), (1, 3, 1, 73),
    (2, 0, 2, 71), (2, 2, 1, 74), (2, 3, 1, 79),
    (3, 0, 3, 76), (3, 3, 1, 73),
]
add("perc", timpani(38, 0.6), TP, 0.4)
add("fx", cymbal(4.0), TP, 0.25)
for i, name in enumerate(("D", "Bm", "G", "A")):
    sv, hv, bass = CH[name]
    t = TP + i * BAR
    add("strings", strings(sv, BAR, att=0.35, rel=0.7, bright=2200), t, 0.5)
    add("choir", choir(hv, BAR, att=0.6, rel=0.8), t, 0.2)
    add("strings", drone(bass, BAR, att=0.1, rel=0.4), t, 0.36)
    for k in range(8):
        m = ARP[name][[0, 1, 2, 1, 3, 2, 1, 2][k]]
        add("piano", piano(m, BEAT * 0.9, 0.34), t + k * BEAT / 2, 0.16, -0.25)
    for b in (0, 2):
        add("perc", timpani(bass + 12 if bass < 36 else bass, 0.4), t + b * BEAT, 0.28)
for bar, beat, beats, m in MEL_P:
    add("piano", piano(m, beats * BEAT * 0.95, 0.62), TP + bar * BAR + beat * BEAT, 0.42, 0.15)
add("fx", cymbal(BAR, swell=True), TP + 3 * BAR, 0.35)

# ---- 65.5 - 75.5 closing ------------------------------------------------------------------
T6 = 65.5
add("perc", timpani(38, 0.7), T6, 0.45)
add("fx", cymbal(5.0), T6, 0.22)
add("choir", choir([62, 66, 69, 74], BAR * 1.2, att=0.05, rel=2.0), T6, 0.35)
add("strings", strings(CH["D"][0], BAR, att=0.05, rel=2.2, bright=2400), T6, 0.6)
add("strings", strings([62, 66, 69], BAR * 2.4, att=1.2, rel=1.2, bright=1800), T6 + BAR * 0.5, 0.42)
add("strings", drone(38, BAR * 2.6, att=0.6, rel=1.0), T6, 0.35)
PIANO_END = [  # (time offset, midi, dur, vel)
    (0.0, 62, 1.2, 0.7), (0.0, 74, 1.2, 0.7), (0.625, 69, 0.6, 0.5), (1.25, 78, 0.6, 0.55),
    (1.875, 76, 0.6, 0.5),
    (2.5, 55, 1.2, 0.55), (2.5, 71, 1.2, 0.6), (3.125, 74, 0.6, 0.48), (3.75, 79, 0.9, 0.52),
    (4.375, 78, 0.6, 0.45),
    (5.0, 50, 2.5, 0.6), (5.0, 57, 2.5, 0.5), (5.0, 66, 2.5, 0.5), (5.0, 74, 2.5, 0.55),
    (5.45, 81, 2.0, 0.35),
]
for dt, m, d, v in PIANO_END:
    add("piano", piano(m, d, v), T6 + dt, 0.6, 0.1 if m > 65 else -0.15)
add("strings", strings([55, 62, 67, 71], BAR, att=0.8, rel=0.8, bright=1700), T6 + BAR, 0.32)
add("strings", strings([50, 57, 62, 64, 69], BAR * 2.2, att=1.5, rel=1.5, bright=1500), T6 + 4.6, 0.36)
add("piano", piano(86, 2.5, 0.3), T6 + 7.6, 0.3, 0.2)


# ---- mix + reverb --------------------------------------------------------------------------------
def make_ir(rt=2.6, pre=0.025):
    n = int((rt + 0.3) * SR)
    t = np.arange(n) / SR
    ir = np.zeros((n, 2))
    for c in range(2):
        nz = rng.standard_normal(n)
        bright = lp(nz, 6000) * np.exp(-t * 6.9 / (rt * 0.55))
        dark = lp(nz, 1500) * np.exp(-t * 6.9 / rt)
        ir[:, c] = (bright * 0.5 + dark) * (t > pre)
        for d, g in ((0.011, 0.5), (0.019, 0.4), (0.027, 0.35), (0.041, 0.25)):   # early reflections
            ir[int((d + c * 0.004) * SR), c] += g * 3
    return ir / np.abs(ir).sum(0).max() * 6


IR = make_ir()
SENDS = {"strings": 0.45, "brass": 0.4, "choir": 0.55, "piano": 0.32, "perc": 0.28, "fx": 0.3}
GAINS = {"strings": 1.0, "brass": 0.8, "choir": 0.75, "piano": 0.9, "perc": 0.85, "fx": 0.55}
mix = np.zeros((N, 2))
wet_in = np.zeros((N, 2))
for k, b in BUSES.items():
    b = b * GAINS[k]
    mix += b
    wet_in += b * SENDS[k]
for c in range(2):
    mix[:, c] += fftconvolve(wet_in[:, c], IR[:, c])[:N] * 0.5
mix[:, 0] = hp(mix[:, 0], 28)
mix[:, 1] = hp(mix[:, 1], 28)

# gentle bus compression (RMS follower) then soft limiting
rms = np.sqrt(lp(np.mean(mix ** 2, 1), 6, 1).clip(1e-9))
ref = np.percentile(rms, 90)
gain = np.minimum(1, (rms / ref) ** -0.2)
mix *= gain[:, None]
fade = int(0.6 * SR)
end_i = int(END * SR)
mix[end_i - fade:end_i] *= np.linspace(1, 0, fade)[:, None] ** 2
mix[end_i:] = 0
mix = np.tanh(mix / np.abs(mix).max() * 1.4) / np.tanh(1.4) * 0.92
wavfile.write(out_path, SR, (mix[:end_i] * 32767).astype(np.int16))
print(f"wrote {out_path} ({END:.1f}s)")
