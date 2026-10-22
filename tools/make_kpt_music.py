"""Generate a royalty-free, feel-good indie-electronic track for the KPT reel (30 s).

120 BPM in A major, I-V-vi-IV (A E F#m D), one chord per 2-second bar. The arrangement
follows the edit:
  0.0-3.0   hook      : impact, full beat, lead hook
  3.0-9.0   booth     : bouncy groove, plucks, offbeat bass
  9.0-17.0  talk      : lighter groove (softer kick, 8th plucks), gentle quote dip at
                        12.6-14.0, snare build 15.0-17.0 straight into the drop
  17.0-24.0 montage   : full chorus, lead an octave up, impact on 21.0 (BIG IMPACT)
  24.0-30.0 ending    : half-time drums, bells, final tonic chord at 28.0 ringing out

Usage: python3 make_kpt_music.py OUT.wav
"""
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt, fftconvolve

SR = 44100
BPM = 120
BEAT = 60 / BPM
BAR = 4 * BEAT
LEN = 31.0
N = int(LEN * SR)
rng = np.random.default_rng(11)
out_path = sys.argv[1] if len(sys.argv) > 1 else "kpt_music.wav"

L = np.zeros(N)
R = np.zeros(N)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def filt(x, kind, fc, order=2):
    if kind == "band":
        wn = [fc[0] / (SR / 2), fc[1] / (SR / 2)]
    else:
        wn = min(fc, SR / 2 - 200) / (SR / 2)
    return sosfilt(butter(order, wn, kind, output="sos"), x)


def adsr(n, a, d, s, r):
    e = np.full(n, s, dtype=float)
    an, dn, rn = max(1, int(a * SR)), max(1, int(d * SR)), max(1, int(r * SR))
    an = min(an, n)
    e[:an] = np.linspace(0, 1, an)
    d_end = min(n, an + dn)
    e[an:d_end] = np.linspace(1, s, d_end - an)
    rn = min(rn, n)
    e[-rn:] *= np.linspace(1, 0, rn)
    return e


def saw(f, n, detune=(-0.1, 0.0, 0.1)):
    t = np.arange(n) / SR
    s = np.zeros(n)
    for d in detune:
        s += 2 * ((t * f * 2 ** (d / 12) + rng.random()) % 1) - 1
    return s / len(detune)


def add(sig, t, g=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N or i + len(sig) <= 0:
        return
    j = min(N, i + len(sig))
    seg = sig[: j - i] * g
    L[i:j] += seg * np.sqrt(0.5 * (1 - pan))
    R[i:j] += seg * np.sqrt(0.5 * (1 + pan))


# ---- sections ----------------------------------------------------------------
def sec(t):
    if t < 3.0:
        return "hook"
    if t < 9.0:
        return "booth"
    if t < 17.0:
        return "talk"
    if t < 24.0:
        return "montage"
    return "ending"


ROOTS = [45, 40, 42, 38]                      # A2 E2 F#2 D2
TRIADS = [[64, 69, 73], [64, 68, 71], [66, 69, 73], [62, 66, 69]]  # around A4
MEL = [
    [76, None, 73, 76, 78, None, 76, None],
    [76, None, 76, 74, 73, None, 71, None],
    [73, None, 76, None, 78, None, 76, 73],
    [74, None, 73, None, 69, None, 71, None],
]


def chord_at(t):
    return int(t // BAR) % 4


# ---- instruments -------------------------------------------------------------
def kick(g=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t / 0.035)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.22)
    click = filt(rng.standard_normal(n), "high", 2500) * np.exp(-t / 0.004) * 0.35
    return np.tanh(1.6 * (body + click)) * g


def clap():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = filt(rng.standard_normal(n), "band", (900, 5000))
    env = np.zeros(n)
    for k, off in enumerate((0.0, 0.011, 0.022)):
        i = int(off * SR)
        env[i:] += np.exp(-(t[: n - i]) / (0.008 if k < 2 else 0.12))
    return noise * env * 0.6


def snare():
    n = int(0.25 * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) * 0.5
    nz = filt(rng.standard_normal(n), "high", 1500) * np.exp(-t / 0.09)
    return (tone + nz) * 0.55


def hat(open_=False):
    n = int((0.22 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    nz = filt(rng.standard_normal(n), "high", 7000)
    return nz * np.exp(-t / (0.07 if open_ else 0.012)) * (0.28 if open_ else 0.22)


def pluck(m, dur=0.22, bright=4500):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(hz(m), n, (-0.05, 0.05)) * 0.6 + np.sin(2 * np.pi * hz(m) * t) * 0.5
    s = filt(s, "low", bright) * np.exp(-t / (dur * 0.35))
    return s * adsr(n, 0.002, 0.05, 1.0, 0.03)


def bell(m, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = hz(m)
    mod = np.sin(2 * np.pi * f * 3.5 * t) * 2.2 * np.exp(-t / 0.3)
    s = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / (dur * 0.4))
    return s * adsr(n, 0.003, 0.1, 1.0, 0.2) * 0.4


def pad(notes, dur, cutoff=2600):
    n = int(dur * SR)
    s = np.zeros(n)
    for m in notes:
        s += saw(hz(m), n, (-0.12, -0.04, 0.04, 0.12))
    s = filt(s / len(notes), "low", cutoff)
    return s * adsr(n, 0.05, 0.2, 0.85, 0.5)


def bass(m, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = saw(hz(m), n, (0.0,)) * 0.6 + np.sin(2 * np.pi * hz(m) * t) * 0.8
    return np.tanh(1.3 * filt(s, "low", 700)) * adsr(n, 0.004, 0.08, 0.8, 0.04)


def lead(m, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.2, 0, 1)
    ph = 2 * np.pi * np.cumsum(hz(m) * vib) / SR
    sq = np.sign(np.sin(ph)) * 0.35 + (2 * ((ph / (2 * np.pi)) % 1) - 1) * 0.4
    return filt(sq, "low", 3800) * adsr(n, 0.01, 0.1, 0.75, 0.08)


def riser(dur, f0=300, f1=6000):
    n = int(dur * SR)
    t = np.arange(n) / SR
    nz = rng.standard_normal(n)
    out = np.zeros(n)
    steps = 24
    for k in range(steps):
        a, b = k * n // steps, (k + 1) * n // steps
        fc = f0 * (f1 / f0) ** (k / steps)
        out[a:b] = filt(nz, "band", (fc * 0.7, min(fc * 1.4, SR / 2 - 500)))[a:b]
    return out * (t / dur) ** 2 * 0.5


def impact(g=1.0):
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (38 + 40 * np.exp(-t / 0.08)) * t) * np.exp(-t / 0.7)
    crash = filt(rng.standard_normal(n), "high", 3000) * np.exp(-t / 0.9) * 0.35
    return np.tanh(1.4 * (boom + crash)) * g


# ---- sidechain pump (applied to chords/bass) --------------------------------
tt = np.arange(N) / SR
phase = (tt % BEAT) / BEAT
pump = 1 - 0.3 * (1 - np.clip(phase / 0.5, 0, 1)) ** 2

# ---- arrangement -------------------------------------------------------------
music_L, music_R = np.zeros(N), np.zeros(N)
beats = np.arange(0, 30.0, BEAT)
for b in beats:
    s = sec(b)
    bi = int(round(b / BEAT))
    on_bar = bi % 4 == 0
    if s == "ending":
        if b >= 28.0:
            continue
        if bi % 4 == 0:
            add(kick(0.9), b)
        if bi % 4 == 2:
            add(snare() * 0.8, b, pan=0.05)
            add(clap() * 0.5, b)
        add(hat(), b + BEAT / 2, 0.8, 0.3)
        continue
    # kick: four-on-the-floor throughout, softer in the talk section
    add(kick(0.95 if s != "talk" else 0.75), b)
    if bi % 2 == 1 and s != "talk":
        add(clap(), b, 0.9, -0.05)
    if s == "talk" and bi % 2 == 1:
        add(clap(), b, 0.45)
    # hats: offbeat open hats + 16th closed hats in high-energy parts
    add(hat(True), b + BEAT / 2, 0.8 if s in ("hook", "montage") else 0.6, 0.25)
    if s in ("hook", "montage", "booth"):
        for k in (1, 3):
            add(hat(), b + k * BEAT / 4, 0.7, -0.3)

# snare build into the drop
for k in range(24):
    t = 15.0 + 2.0 * (1 - (1 - k / 24) ** 1.35)   # accelerating roll, lands on 17.0
    add(snare(), t, 0.2 + 0.45 * k / 23, 0.1)

# bass: offbeat eighths (pumping), root of the bar
for b in np.arange(0, 28.0, BEAT / 2):
    s = sec(b)
    root = ROOTS[chord_at(b)]
    if s == "ending":
        if (b / BEAT) % 2 == 0:
            add(bass(root, BEAT * 2.05), b, 0.5)
        continue
    if round(b / (BEAT / 2)) % 2 == 1:        # offbeat eighths only
        add(bass(root, BEAT * 0.98), b, 0.55)

# chords: pumping pad, one per bar
for bar in range(15):
    t0 = bar * BAR
    notes = TRIADS[bar % 4]
    if t0 >= 28.0:
        break
    p = pad([n - 12 for n in notes] + notes, BAR + 0.45, 2200 if sec(t0) != "ending" else 1600)
    g = {"hook": 0.36, "booth": 0.3, "talk": 0.32, "montage": 0.38, "ending": 0.4}[sec(t0)]
    i = int(t0 * SR)
    j = min(N, i + len(p))
    add(p[: j - i] * (pump[i:j] if sec(t0) != "ending" else 1.0), t0, g, 0.0)

# final tonic chord, ringing out
fin = pad([45, 57, 64, 69, 73, 76], 3.0, 1800)
add(fin, 28.0, 0.42)
add(impact(0.5), 28.0)
for k, m in enumerate([69, 73, 76, 81]):
    add(bell(m, 2.6), 28.0 + k * 0.12, 0.5, -0.4 + 0.25 * k)

# pluck arpeggio: 16ths in booth/montage, 8ths in talk, bells in the ending
for b in np.arange(0, 28.0, BEAT / 4):
    s = sec(b)
    k = int(round(b / (BEAT / 4)))
    tri = TRIADS[chord_at(b)]
    pattern = [tri[0], tri[1], tri[2], tri[1] + 12 if tri[1] + 12 < 88 else tri[1]]
    m = pattern[k % 4] + 12
    if s in ("booth", "montage", "hook"):
        add(pluck(m), b, 0.16 if s != "booth" else 0.2, 0.35 if k % 2 else -0.35)
    elif s == "talk" and k % 2 == 0:
        add(pluck(m, 0.3, 3000), b, 0.17, 0.3 if k % 4 else -0.3)
    elif s == "ending" and k % 4 == 0:
        add(bell(m, 1.4), b, 0.22, 0.3 if k % 8 else -0.3)

# lead hook: hook section and the montage chorus (octave up)
for b in np.arange(0, 24.0, BEAT / 2):
    s = sec(b)
    if s not in ("hook", "montage"):
        continue
    bar = int(b // BAR) % 4
    step = int(round((b % BAR) / (BEAT / 2)))
    m = MEL[bar][step]
    if m is None:
        continue
    up = 12 if s == "montage" and b >= 21.0 else 0
    nxt = step + 1
    ln = 1
    while nxt < 8 and MEL[bar][nxt] is None:
        ln += 1
        nxt += 1
    add(lead(m + up, ln * BEAT / 2 * 0.95), b, 0.22, 0.1)

# fx: impacts on the big moments, risers into section changes
for t, g in ((0.0, 0.9), (9.0, 0.45), (17.0, 0.8), (21.0, 0.7), (24.0, 0.4)):
    add(impact(g), t)
for t_end, dur, g in ((3.0, 1.0, 0.35), (9.0, 1.5, 0.4), (17.0, 2.0, 0.6), (24.0, 1.5, 0.4)):
    add(riser(dur), t_end - dur, g)

# ---- quote dip: lowpass the whole bed while Dr Azren speaks -------------------
mix = np.stack([L, R])
lp = np.stack([filt(L, "low", 2200), filt(R, "low", 2200)])
w = 0.6 * np.clip(np.minimum((tt - 12.45) / 0.3, (14.05 - tt) / 0.35), 0, 1)
mix = mix * (1 - w) + lp * w

# ---- reverb + master ---------------------------------------------------------
ir_n = int(1.6 * SR)
ir_t = np.arange(ir_n) / SR
irL = rng.standard_normal(ir_n) * np.exp(-ir_t / 0.45)
irR = rng.standard_normal(ir_n) * np.exp(-ir_t / 0.45)
irL, irR = filt(irL, "low", 6000), filt(irR, "low", 6000)
wetL = fftconvolve(mix[0], irL)[:N]
wetR = fftconvolve(mix[1], irR)[:N]
wet = np.stack([wetL, wetR])
wet /= np.max(np.abs(wet)) + 1e-9
mix = mix + wet * 0.12 * np.max(np.abs(mix))
mix = filt(mix[0], "high", 30), filt(mix[1], "high", 30)
mix = np.stack(mix)
mix /= np.max(np.abs(mix)) + 1e-9
mix = np.tanh(1.5 * mix) / np.tanh(1.5)
fade = np.clip((30.0 - tt) / 1.6, 0, 1)
mix *= fade
mix *= 0.9
wavfile.write(out_path, SR, (mix.T * 32767).astype(np.int16))
print(f"wrote {out_path}")
