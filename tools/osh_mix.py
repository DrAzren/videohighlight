"""Mix the reel soundtrack: music bed + synthesized SFX + natural event sound from the footage.

Usage: python3 osh_mix.py EDL.json SRC_DIR AUDIO_DIR
Reads AUDIO_DIR/bgm.wav and AUDIO_DIR/sfx/*.wav, writes AUDIO_DIR/mix.wav normalised to
-14 LUFS / -1.5 dBTP (two-pass loudnorm). Each shot's own sound (cheers, laughter, applause)
sits under the music at the shot's "amb" gain; the music ducks a little when amb >= 0.6.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000
edl = json.loads(Path(sys.argv[1]).read_text())
src_dir, adir = Path(sys.argv[2]), Path(sys.argv[3])
DUR = edl["duration"]
N = int(DUR * SR)


def load(path):
    x, sr = sf.read(path, dtype="float32", always_2d=True)
    assert sr == SR, path
    return x if x.shape[1] == 2 else np.repeat(x, 2, 1)


def src_audio(name, ss, t):
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(ss), "-t", str(t), "-i",
                        str(src_dir / f"{name}.mp4"), "-vn", "-ac", "2", "-ar", str(SR),
                        "-af", "highpass=f=90,lowpass=f=12000", "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2)


def place(buf, sig, t, gain=1.0):
    i = int(round(t * SR))
    s0 = max(0, -i)
    j = min(len(buf), i + len(sig))
    if j > max(i, 0):
        buf[max(i, 0):j] += gain * sig[s0:s0 + j - max(i, 0)]


music = load(adir / "bgm.wav")[:N]
sfx_bus = np.zeros((N, 2), np.float32)
amb_bus = np.zeros((N, 2), np.float32)
duck = np.ones(N, np.float32)

XF = 0.04
for s in edl["shots"]:
    g = s.get("amb", 0)
    if not g:
        continue
    a = src_audio(s["src"], max(0, s["ms"] - XF), s["dur"] + 2 * XF)
    n = len(a)
    fade = np.ones(n, np.float32)
    k = int(XF * 2 * SR)
    fade[:k] = np.linspace(0, 1, k)
    fade[-k:] = np.linspace(1, 0, k)
    place(amb_bus, a * fade[:, None], s["t"] - XF, g)
    if g >= 0.6:
        i0, i1 = int(s["t"] * SR), int((s["t"] + s["dur"]) * SR)
        ramp = int(0.08 * SR)
        d = np.ones(i1 - i0 + 2 * ramp, np.float32) * 0.7
        d[:ramp] = np.linspace(1, 0.7, ramp)
        d[-ramp:] = np.linspace(0.7, 1, ramp)
        lo = max(0, i0 - ramp)
        duck[lo:lo + len(d)] = np.minimum(duck[lo:lo + len(d)], d[: len(duck[lo:lo + len(d)])])

lib = {p.stem: load(p) for p in (adir / "sfx").glob("*.wav")}
for c in edl["sfx"]:
    place(sfx_bus, lib[c["name"]], c["t"] - c.get("align", 0.0), c["gain"])

# event sound is normalised so its loud moments sit ~10 dB under the music peaks
amb_bus *= 0.32 / (np.percentile(np.abs(amb_bus), 99.5) + 1e-9)
mix = music * duck[:, None] + 0.42 * sfx_bus + amb_bus
end = np.ones(N, np.float32)                     # everything resolves into silence at 30 s
fs = int((DUR - 0.8) * SR)
end[fs:] = np.linspace(1, 0, N - fs) ** 1.5
mix *= end[:, None]
raw = adir / "mix_raw.wav"
sf.write(raw, mix, SR, subtype="FLOAT")

# two-pass EBU R128 normalisation
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                   capture_output=True, text=True)
js = json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])
af = ("loudnorm=I=-14:TP=-1.5:LRA=11:linear=true:"
      f"measured_I={js['input_i']}:measured_TP={js['input_tp']}:measured_LRA={js['input_lra']}:"
      f"measured_thresh={js['input_thresh']}:offset={js['target_offset']}")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", af, "-ar", str(SR),
                "-c:a", "pcm_s24le", "-t", str(DUR), str(adir / "mix.wav")], check=True)
raw.unlink()
print(f"wrote {adir / 'mix.wav'} (input {js['input_i']} LUFS -> -14 LUFS)")
