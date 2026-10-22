"""Render the footage layer of a beat-grid reel: every segment is cut to an exact frame
count, so the concatenated result lines up with the music and the motion-graphics overlay.

Usage: python3 render_v4.py cuts.json OUT.mp4 [SEG_DIR]

cuts.json:
{
  "segments": [
    {"t0": 0.0, "t1": 1.5,              # slot on the reel timeline (seconds)
     "src": "work/src/13_x.mp4", "start": 16.9,
     "cx": 0.5,                         # horizontal crop centre (0..1)
     "zoom": [1.04, 1.12],              # push-in from/to over the slot
     "fx": "punch" | "whip" | null,     # entrance: fast zoom-snap or blurred whip
     "speed": 1.0,                      # >1 = faster
     "freeze": 0.5,                     # hold the last frame this long (inside the slot)
     "exp": 0.0,                        # brightness tweak
     "split": [{"src":..,"start":..,"cy":0.4}, {...}],   # top/bottom split screen
     "blank": true}                     # placeholder (fully covered by the overlay)
  ]
}
"""
import json
import subprocess
import sys
from pathlib import Path

W, H, FPS = 1080, 1920, 30

cfg = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
seg_dir = Path(sys.argv[3] if len(sys.argv) > 3 else "work/seg")
seg_dir.mkdir(parents=True, exist_ok=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-3000:]}")


def frames(s):
    return round(s["t1"] * FPS) - round(s["t0"] * FPS)


GRADE = ("cas=strength=0.45,"
         "eq=contrast=1.06:saturation=1.07:gamma=1.03:brightness={exp},"
         "colorbalance=rs=-0.01:bs=0.025:rm=0.0:bm=0.01:rh=0.01:bh=-0.01,"
         "vignette=angle=PI/6")


def stab_filter(src, start, dur, key):
    trf = seg_dir / f"{key}.trf"
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-t", str(dur + 0.2), "-i", src,
         "-vf", f"vidstabdetect=shakiness=6:accuracy=12:result={trf}", "-f", "null", "-"])
    return f"vidstabtransform=input={trf}:smoothing=15:optzoom=1:interpol=bicubic:crop=black,"


def single(s, i):
    n = frames(s)
    dur = n / FPS
    freeze = s.get("freeze", 0.0)
    speed = s.get("speed", 1.0)
    play = dur - freeze
    in_dur = play * speed
    z0, z1 = s.get("zoom", [1.03, 1.09])
    cx = s.get("cx", 0.5)
    fx = s.get("fx")
    # push-in over the slot, plus an eased zoom-snap for "punch" entrances
    z = f"({z0}+({z1}-{z0})*t/{dur:.3f})"
    if fx == "punch":
        z = f"({z}+0.32*pow(max(0,1-t/0.32),3))"
    if fx == "whip":
        z = f"({z}+0.10*pow(max(0,1-t/0.2),2))"
    stab = stab_filter(s["src"], s["start"], in_dur, f"s{i:02d}") if s.get("stab", True) else ""
    # whip: horizontal slide that settles in 0.2 s, motion-blurred while moving
    xoff = "0"
    if fx == "whip":
        xoff = f"(iw-{W})/2*{s.get('whip_dir', 1)}*pow(max(0,1-t/0.2),2)"
    chain = (f"[0:v]{stab}setpts=(PTS-STARTPTS)/{speed},fps={FPS},hqdn3d=1.5:1.5:3:3,"
             f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={W}:{H}:(iw-{W})*{cx}:(ih-{H})/2,"
             f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=lanczos,"
             f"crop={W}:{H}:'(iw-{W})*{cx}+{xoff}':'(ih-{H})/2',setsar=1,")
    if fx == "whip":
        chain += "gblur=sigma=28:sigmaV=0.01:enable='lt(t,0.14)',"
    chain += GRADE.format(exp=s.get("exp", 0.0))
    if freeze:
        chain += f",trim=end_frame={round(play * FPS)},tpad=stop_mode=clone:stop_duration={freeze + 0.1}"
    chain += "[v]"
    return ["-ss", str(s["start"]), "-t", f"{in_dur + 0.3:.3f}", "-i", s["src"]], chain


def split(s, i):
    n = frames(s)
    dur = n / FPS
    args, parts = [], []
    hh = H // 2
    for k, p in enumerate(s["split"]):
        args += ["-ss", str(p["start"]), "-t", f"{dur + 0.3:.3f}", "-i", p["src"]]
        z = f"(1.02+0.06*t/{dur:.3f})"
        parts.append(
            f"[{k}:v]setpts=PTS-STARTPTS,fps={FPS},hqdn3d=1.5:1.5:3:3,"
            f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{hh}:(iw-{W})*{p.get('cx', 0.5)}:(ih-{hh})*{p.get('cy', 0.4)},"
            f"scale=w='trunc({W}*{z}/2)*2':h='trunc({hh}*{z}/2)*2':eval=frame:flags=lanczos,"
            f"crop={W}:{hh},setsar=1,{GRADE.format(exp=p.get('exp', 0.0))}[p{k}]")
    return args, ";".join(parts) + ";[p0][p1]vstack[v]"


clips = []
for i, s in enumerate(cfg["segments"]):
    n = frames(s)
    o = seg_dir / f"s{i:02d}.mp4"
    spec = seg_dir / f"s{i:02d}.json"
    key = json.dumps(s, sort_keys=True)
    if o.exists() and spec.exists() and spec.read_text() == key:   # unchanged: reuse
        clips.append(o)
        print(f"segment {i + 1}/{len(cfg['segments'])}: cached")
        continue
    if s.get("blank"):
        args, chain = ["-f", "lavfi", "-i", f"color=c=0x0b1736:s={W}x{H}:r={FPS}"], "[0:v]null[v]"
    elif s.get("split"):
        args, chain = split(s, i)
    else:
        args, chain = single(s, i)
    run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", chain, "-map", "[v]",
         "-frames:v", str(n), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "12",
         "-pix_fmt", "yuv420p", "-an", str(o)])
    got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v",
                              "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(o)],
                             capture_output=True, text=True).stdout.strip())
    if got != n:
        sys.exit(f"segment {i}: expected {n} frames, got {got}")
    spec.write_text(key)
    clips.append(o)
    print(f"segment {i + 1}/{len(cfg['segments'])}: {s['t0']:.2f}-{s['t1']:.2f}s ({n} frames)")

lst = seg_dir / "list.txt"
lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
     "-c", "copy", str(out)])
print(f"wrote {out}")
