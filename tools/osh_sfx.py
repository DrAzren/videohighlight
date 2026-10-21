"""Synthesize the reel's sound-effect library (original, royalty-free, no attribution needed).

Usage: python3 osh_sfx.py OUT_DIR
Writes whoosh, pop, shutter, impact_soft, impact_big, sparkle, riser_short (48 kHz stereo).
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(7)
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)


def bp(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo / (SR / 2), min(hi, SR / 2 - 100) / (SR / 2)], "band", output="sos"), x)


def lp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), "low", output="sos"), x)


def hp(x, fc, order=2):
    return sosfilt(butter(order, fc / (SR / 2), "high", output="sos"), x)


def sweep_noise(dur, f0, f1, q=0.6):
    n = int(dur * SR)
    noise = rng.standard_normal(n + 4000)
    y = np.zeros(n)
    seg = int(0.01 * SR)
    for i in range(0, n, seg):
        f = f0 * (f1 / f0) ** (i / n)
        y[i:i + seg] = bp(noise[i:i + seg + 4000], f * (1 - q / 2), f * (1 + q / 2))[: min(seg, n - i)]
    return y


def stereo(x, pan=0.0):
    l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
    return np.stack([x * l, x * r], 1)


def save(name, x):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    sf.write(out / f"{name}.wav", x.astype(np.float32), SR)


# whoosh: band-passed noise sweeping up then down, panned across
n = int(0.42 * SR); t = np.arange(n) / SR
w = sweep_noise(0.42, 500, 5000) * np.sin(np.pi * t / 0.42) ** 2
pan = np.linspace(-0.8, 0.8, n)
save("whoosh", np.stack([w * np.sqrt(0.5 * (1 - pan)), w * np.sqrt(0.5 * (1 + pan))], 1))

# pop: quick rising sine blip + click
n = int(0.12 * SR); t = np.arange(n) / SR
f = 380 + 900 * (t / 0.12) ** 0.5
pop = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38)
pop += 0.3 * hp(rng.standard_normal(n), 3000) * np.exp(-t * 400)
save("pop", stereo(pop))

# camera shutter: two mechanical clicks with a short whirr between
n = int(0.22 * SR); t = np.arange(n) / SR
sh = np.zeros(n)
for at, g in [(0.0, 1.0), (0.085, 0.8)]:
    i = int(at * SR)
    k = np.arange(n - i) / SR
    sh[i:] += g * bp(rng.standard_normal(n - i), 1500, 9000) * np.exp(-k * 160)
    sh[i:] += g * 0.5 * np.sin(2 * np.pi * 2300 * k) * np.exp(-k * 220)
sh += 0.12 * bp(rng.standard_normal(n), 600, 2400) * ((t > 0.01) & (t < 0.085))
save("shutter", stereo(sh))

# soft impact: low thump + air
n = int(0.7 * SR); t = np.arange(n) / SR
f = 48 + 70 * np.exp(-t * 18)
imp = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
imp += 0.25 * lp(rng.standard_normal(n), 1500) * np.exp(-t * 14)
save("impact_soft", stereo(np.tanh(1.5 * imp)))

# big impact (opening hit): sub boom + noise burst + metallic tail
n = int(1.8 * SR); t = np.arange(n) / SR
f = 38 + 110 * np.exp(-t * 10)
big = 1.1 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6)
big += 0.5 * bp(rng.standard_normal(n), 200, 6000) * np.exp(-t * 9)
big += 0.15 * hp(rng.standard_normal(n), 5000) * np.exp(-t * 2.2)
save("impact_big", stereo(np.tanh(1.4 * big)))

# sparkle: scattered high bell glints
n = int(1.1 * SR); t = np.arange(n) / SR
sp = np.zeros((n, 2))
for k in range(11):
    at = 0.035 * k + rng.random() * 0.03
    i = int(at * SR)
    m = n - i
    kk = np.arange(m) / SR
    fr = 2200 * 2 ** (rng.integers(0, 14) / 12)
    g = np.sin(2 * np.pi * fr * kk) * np.exp(-kk * 9) + 0.4 * np.sin(2 * np.pi * fr * 2.7 * kk) * np.exp(-kk * 15)
    p = rng.uniform(-0.7, 0.7)
    sp[i:, 0] += g * np.sqrt(0.5 * (1 - p)) * (1 - k / 14)
    sp[i:, 1] += g * np.sqrt(0.5 * (1 + p)) * (1 - k / 14)
save("sparkle", sp)

# short riser (1 s) into the happy montage
n = int(1.0 * SR); t = np.arange(n) / SR
r = sweep_noise(1.0, 300, 9000, 0.5) * (t / 1.0) ** 2
fr = 180 * 2 ** (2.5 * t)
r += 0.15 * lp(2 * ((np.cumsum(fr) / SR) % 1) - 1, 2500) * (t / 1.0) ** 2
save("riser_short", stereo(r))
print("sfx written to", out)
