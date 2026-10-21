"""Render the graded 9:16 footage plates for a highlight reel from its edit list.

Usage: python3 osh_plates.py EDL.json SRC_DIR OUT_DIR [SHOT_ID ...]

For every shot: trim -> stabilise (vidstab, 2-pass) -> retime (speed ramps, blended
slow motion) -> exposure match -> denoise -> bright cheerful grade (natural skin via
vibrance, warm highlights, clean shadows) -> exactly dur*fps frames, H.264, no audio.
A shot with "freeze_at" holds that frame for the rest of its slot and also writes
OUT_DIR/<id>_freeze.png. A still shot writes a 2x graded JPG for the Ken Burns move.
"""
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

edl = json.loads(Path(sys.argv[1]).read_text())
src_dir, out = Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
W, H, FPS = edl["canvas"]["w"], edl["canvas"]["h"], edl["canvas"]["fps"]
tmp = Path(tempfile.mkdtemp(prefix="plates_"))
TARGET_Y = 118.0   # mean luma the grade aims for (0-255)

GRADE = ("eq=contrast=1.06:saturation=1.04,vibrance=intensity=0.22,"
         "colorbalance=rs=-0.01:bs=0.025:rm=0.01:rh=0.045:gh=0.018:bh=-0.035,"
         "cas=strength=0.35")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"failed: {' '.join(map(str, cmd))}\n{r.stderr[-2500:]}")
    return r


def mean_luma(path, ss=None, t=None):
    trim = ["-ss", str(ss), "-t", str(t)] if ss is not None else []
    r = run(["ffmpeg", "-v", "error", *trim, "-i", str(path), "-vf",
             "scale=270:-2,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
             "-f", "null", "-"])
    vals = [float(l.split("=")[1]) for l in r.stdout.splitlines() if "YAVG" in l]
    return sum(vals) / max(1, len(vals))


def gamma_for(y):
    # lift dim / backlit shots toward TARGET_Y, never darken bright ones much
    g = math.log(TARGET_Y / 255) / math.log(max(y, 20) / 255)
    return round(min(1.45, max(0.92, 1 / g)), 3)


only = set(sys.argv[4:])
for s in edl["shots"]:
    sid = s["id"]
    if only and sid not in only:
        continue
    if s.get("still"):
        src = src_dir / f"{s['src']}.jpg"
        y = mean_luma(src)
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf",
             f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={W*2}:{H*2},eq=gamma={gamma_for(y)},{GRADE}",
             "-q:v", "2", str(out / f"{sid}.jpg")])
        print(f"{sid} still  Y={y:.0f}")
        continue

    src = src_dir / f"{s['src']}.mp4"
    speed, dur = s.get("speed", 1.0), s["dur"]
    hold = s.get("freeze_at")
    play = hold if hold is not None else dur
    span = play * speed + 0.2                      # source seconds needed (+ margin)
    y = mean_luma(src, s["ms"], span)
    trf = tmp / f"{sid}.trf"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["ms"]), "-t", str(span), "-i", str(src),
         "-vf", f"vidstabdetect=shakiness=7:accuracy=12:result={trf}", "-f", "null", "-"])
    retime = f"setpts=PTS/{speed}"
    if speed < 1:
        retime += f",minterpolate=fps={FPS}:mi_mode=blend"
    vf = (f"vidstabtransform=input={trf}:smoothing=14:optzoom=1:interpol=bicubic,"
          f"{retime},fps={FPS},hqdn3d=1.5:1.5:3:3,"
          f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
          f"eq=gamma={gamma_for(y)},{GRADE},setsar=1,format=yuv420p")
    frames = round(play * FPS)
    if hold is not None:
        vf += f",trim=end_frame={frames},tpad=stop_mode=clone:stop={round(dur*FPS) - frames}"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["ms"]), "-t", str(span), "-i", str(src),
         "-vf", vf, "-an", "-frames:v", str(round(dur * FPS)), "-c:v", "libx264",
         "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         str(out / f"{sid}.mp4")])
    if hold is not None:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(out / f"{sid}.mp4"), "-vf",
             f"select=eq(n\\,{frames - 1})", "-frames:v", "1", str(out / f"{sid}_freeze.png")])
    print(f"{sid} {s['src']}@{s['ms']} x{speed} Y={y:.0f} gamma={gamma_for(y)}")
