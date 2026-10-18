"""Clean up and tighten the speech excerpts used in the film.

Usage: python3 edit_speech.py EDL.json SRC_DIR WORK_DIR

For every entry in EDL "speech_edits":
  {"name", "src", "start", "end", "max_gap": 0.2, "gap": 0.12, "atten": null}
1. Noise reduction. These are phone recordings of a hall PA, and DeepFilterNet tends
   to swallow soft syllables in them ("adab", "hikmah" disappeared at 12-28 dB), so by
   default (atten null) the original audio is kept and only a light spectral denoise
   (afftdn) is applied; set atten to a dB limit to use DeepFilterNet3 instead
   (needs `pip install deepfilternet torch torchaudio`).
2. Pauses and hesitation gaps longer than `max_gap` (no speech energy within 38 dB of
   the phrase peak, measured on a fully denoised copy so residual hall noise cannot
   mask a pause) are shortened to `gap`, with 30 ms equal-power crossfades at
   every join, so words follow each other naturally. Words are never cut or reordered.
3. Voice polish: rumble cut, de-mud, presence and air lift and levelling compression
   (a de-esser and short room were tried and dropped: they blurred consonants, e.g.
   "bicara" was heard as "bincangan").
Writes WORK_DIR/speech_<name>.wav (48 kHz stereo) and prints every cut it made.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
from df.enhance import enhance, init_df
from scipy.io import wavfile
from scipy.ndimage import uniform_filter1d

SR = 48000
edl = json.loads(Path(sys.argv[1]).read_text())
SRC, WORK = Path(sys.argv[2]), Path(sys.argv[3])
WORK.mkdir(parents=True, exist_ok=True)
model, df_state, _ = init_df(log_level="ERROR")

POLISH = ("highpass=f=85:p=2,afftdn=nr=8:nf=-38:tn=1,"
          "equalizer=f=220:t=q:w=1.2:g=-3,"
          "equalizer=f=650:t=q:w=1.5:g=-1.5,"
          "equalizer=f=3400:t=q:w=1.4:g=3,"
          "highshelf=f=9000:g=2,"
          "acompressor=threshold=-26dB:ratio=2.5:attack=8:release=140:makeup=3,"
          "alimiter=limit=0.89")


def load(src, a, b):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, a):.3f}", "-t", f"{b - max(0, a):.3f}",
                        "-i", str(src), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def voiced(x):
    hop = SR // 100
    e = np.sqrt(uniform_filter1d(x.astype(np.float64) ** 2, hop)[::hop] + 1e-12)
    db = uniform_filter1d(20 * np.log10(e), 3)
    on = db > db.max() - 38
    # bridge micro-gaps inside words (< 60 ms) and drop isolated clicks (< 40 ms)
    on = uniform_filter1d(on.astype(float), 7) > 0.2
    return on, hop


def tighten(y, detect, max_gap, gap):
    on, hop = voiced(detect)
    keep = np.ones(len(y), bool)
    cuts = []
    i = 0
    while i < len(on):
        if not on[i]:
            j = i
            while j < len(on) and not on[j]:
                j += 1
            s, e = i * hop, j * hop
            if 0 < i and j < len(on) and (e - s) / SR > max_gap:
                drop = int((e - s) - gap * SR)
                a = s + int(gap * SR / 2)
                keep[a:a + drop] = False
                cuts.append((s / SR, e / SR))
            i = j
        else:
            i += 1
    # assemble with equal-power crossfades at every join
    xf = int(0.03 * SR)
    out = np.zeros(0, np.float32)
    idx = np.flatnonzero(np.diff(np.r_[0, keep.astype(int), 0]))
    for a, b in zip(idx[::2], idx[1::2]):
        piece = y[a:b].astype(np.float32)
        if len(out) >= xf and len(piece) >= xf:
            t = np.linspace(0, np.pi / 2, xf)
            out[-xf:] = out[-xf:] * np.cos(t) + piece[:xf] * np.sin(t)
            out = np.concatenate([out, piece[xf:]])
        else:
            out = np.concatenate([out, piece])
    return out, cuts


for sp in edl["speech_edits"]:
    a, b = sp["start"], sp["end"]
    ctx = 1.0
    x = load(SRC / sp["src"], a - ctx, b + ctx)
    lead = int(min(ctx, a) * SR)
    n = int((b - a) * SR)
    lim = sp.get("atten")
    y = x if lim is None else enhance(model, df_state, torch.from_numpy(x)[None], atten_lim_db=lim)[0].numpy()
    full = enhance(model, df_state, torch.from_numpy(x)[None], atten_lim_db=None)[0].numpy()
    y, cuts = tighten(y[lead:lead + n], full[lead:lead + n], sp.get("max_gap", 0.2), sp.get("gap", 0.12))
    f = 0.015 * SR
    y[:int(f)] *= np.linspace(0, 1, int(f))
    y[-int(f):] *= np.linspace(1, 0, int(f))
    raw = WORK / f"speech_{sp['name']}_tight.wav"
    wavfile.write(raw, SR, (y / (np.abs(y).max() + 1e-9) * 0.7).astype(np.float32))
    out = WORK / f"speech_{sp['name']}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", POLISH + ",aformat=channel_layouts=stereo",
                    "-ar", str(SR), "-c:a", "pcm_s24le", str(out)], check=True)
    print(f"{sp['name']}: {b - a:.2f}s -> {len(y) / SR:.2f}s; shortened pauses at "
          + ", ".join(f"{a + s:.2f}-{a + e:.2f} ({e - s:.2f}s)" for s, e in cuts), flush=True)
