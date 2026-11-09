"""Cut a 9:16 highlight reel from real footage, mix stage audio + ambience + music,
and composite a transparent HyperFrames overlay on top.

Usage: python3 reel_edit.py cuts.json OUT.mp4 [--no-overlay] [--draft]

cuts.json:
{
  "media": "work/media",                 # folder with the source clips
  "music": "work/music.wav",             # full-length music already aligned to t=0
  "overlay": "work/overlay.mov",         # ProRes 4444 alpha from HyperFrames (optional)
  "segments": [
    {"src": "45.mp4", "in": 16.45, "dur": 4.45,
     "z0": 1.12, "z1": 1.18,             # zoom at start / end (1 = full frame)
     "fx": 0.55, "fy": 0.45,             # focus point (0..1) the zoom is centred on
     "rate": 1.0,                        # playback speed (0.5 = slow motion, silent)
     "voice": true,                      # stage speech: full level, music ducks under it
     "amb": 0.3}                         # gain for non-voice natural sound (hall ambience)
  ]
}
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

W, H, FPS, SR = 1080, 1920, 30, 48000

cfg_path = Path(sys.argv[1])
cfg = json.loads(cfg_path.read_text())
out = Path(sys.argv[2])
use_overlay = "--no-overlay" not in sys.argv and cfg.get("overlay")
draft = "--draft" in sys.argv
media = Path(cfg["media"])
tmp = Path(tempfile.mkdtemp(prefix="reel_"))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{' '.join(map(str, cmd))}\n{r.stderr[-3000:]}")
    return r


def segment(i, s, n):
    """Render one shot to an intermediate 1080x1920/30 fps clip with stereo audio."""
    src = media / s["src"]
    dur = s["dur"]
    rate = s.get("rate", 1.0)
    src_dur = dur * rate
    z0 = s.get("z0", 1.0)
    z1 = s.get("z1", z0 * 1.04)
    fx, fy = s.get("fx", 0.5), s.get("fy", 0.5)
    dur = n / FPS
    is_img = src.suffix.lower() in (".jpg", ".jpeg", ".png")

    # Work at 2x so the Ken-Burns crop moves in half-pixel steps (no jitter),
    # cover-fit the source into 9:16, then zoompan around the focus point.
    up = 2
    WW, HH = W * up, H * up
    zexpr = f"({z0}+({z1}-{z0})*on/{max(n - 1, 1)})"
    xexpr = f"max(0,min(iw-iw/zoom,{fx}*iw-iw/zoom/2))"
    yexpr = f"max(0,min(ih-ih/zoom,{fy}*ih-ih/zoom/2))"
    vf = []
    if not is_img:
        vf.append(f"setpts=(PTS-STARTPTS)/{rate}" if rate != 1.0 else "setpts=PTS-STARTPTS")
        vf.append(f"fps={FPS}")
    vf += [
        f"scale={WW}:{HH}:force_original_aspect_ratio=increase:flags=lanczos",
        # cx -> cx1 pans the 9:16 window across a wider (landscape) source over the shot
        f"crop={WW}:{HH}:'(iw-{WW})*({s.get('cx', 0.5)}+({s.get('cx1', s.get('cx', 0.5))}-{s.get('cx', 0.5)})"
        f"*min(t/{dur},1))':(ih-{HH})*{s.get('cy', 0.5)}",
        f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':d=1:s={W}x{H}:fps={FPS}",
        "hqdn3d=1.5:1.2:3:3",
        # warm, lifted grade shared by every shot so the cut feels like one film
        "eq=contrast=1.06:saturation=1.12:gamma=1.03",
        "colorbalance=rs=0.015:gs=0.0:bs=-0.025:rm=0.02:bm=-0.02:rh=0.01:bh=-0.015",
        "cas=strength=0.35",
        "setsar=1,format=yuv420p",
    ]
    v_in = (["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(src)] if is_img
            else ["-ss", f"{s['in']:.3f}", "-t", f"{src_dur + 0.1:.3f}", "-i", str(src)])
    outp = tmp / f"s{i:02d}.mov"

    # audio: voice segments at full level (loudness-matched), the rest as quiet ambience.
    # Slow-motion and photo shots carry no source sound.
    if is_img or rate != 1.0:
        a_in = ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={SR}:cl=stereo"]
        af = "anull"
    else:
        a_in = []
        g = 1.0 if s.get("voice") else s.get("amb", 0.25)
        af = (f"aresample={SR},pan=stereo|c0=c0|c1=c0," if s.get("mono", True) else f"aresample={SR},")
        af += "highpass=f=90,lowpass=f=12000,"
        if s.get("voice"):
            # gentle clean-up + leveller so every stage line sits at the same loudness
            af += "afftdn=nr=10:nf=-40,acompressor=threshold=-24dB:ratio=3:attack=5:release=120:makeup=4,"
            af += f"loudnorm=I=-16:TP=-2:LRA=7,"
        else:
            af += "loudnorm=I=-20:TP=-3:LRA=9,"
        af += f"volume={g * s.get('gain', 1.0)},"
        # 30 ms fades kill clicks at the cut
        af += f"afade=t=in:d=0.03,afade=t=out:st={max(dur - 0.04, 0):.3f}:d=0.04"
        af += f",atrim=0:{dur:.3f}"
    cmd = ["ffmpeg", "-v", "error", "-y", *v_in, *a_in,
           "-filter_complex", f"[0:v]{','.join(vf)},trim=end_frame={n}[v];"
                              f"[{1 if a_in else 0}:a]{af},apad,atrim=0:{dur:.3f}[a]",
           "-map", "[v]", "-map", "[a]", "-frames:v", str(n),
           "-c:v", "libx264", "-preset", "veryfast" if draft else "slow", "-crf", "24" if draft else "12",
           "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2", str(outp)]
    run(cmd)
    return outp, n / FPS


parts, t, voice_spans, planned = [], 0.0, [], 0.0
for i, s in enumerate(cfg["segments"]):
    # frame counts follow the planned cumulative cut times, so rounding never drifts off the beat grid
    n = round((planned + s["dur"]) * FPS) - round(planned * FPS)
    planned += s["dur"]
    p, d = segment(i, s, n)
    parts.append(p)
    if s.get("voice"):
        voice_spans.append((t + s.get("voice_from", 0.0), t + d - s.get("voice_trim_end", 0.0)))
    print(f"[{i:02d}] {t:6.2f}-{t + d:6.2f}  {s['src']:>8} @ {s.get('in', 0):6.2f}  "
          f"{'VOICE' if s.get('voice') else ''}", flush=True)
    t += d
total = t
print(f"total {total:.2f}s")

lst = tmp / "list.txt"
lst.write_text("".join(f"file '{p}'\n" for p in parts))
base = tmp / "base.mov"
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])

# Music envelope: ducks to `duck` under stage speech with short ramps.
duck, ramp = cfg.get("duck_db", -15), 0.35
mus_gain = cfg.get("music_db", -4)
expr = "1"
for a, b in voice_spans:
    lo = 10 ** (duck / 20)
    # piecewise-linear dip: ramp down before a, hold, ramp up after b
    expr = (f"if(between(t,{a - ramp:.3f},{b + ramp:.3f}),"
            f"min({expr},max({lo},max(({a:.3f}-t)/{ramp},(t-{b:.3f})/{ramp})*(1-{lo})+{lo})),{expr})")
music_start = cfg.get("music_start", 0.0)

final_v = "[0:v]"
inputs = ["-i", str(base), "-i", cfg["music"]]
fc = []
if use_overlay:
    inputs += ["-i", cfg["overlay"]]
    fc.append(f"[2:v]format=yuva444p,setpts=PTS-STARTPTS[ov];[0:v][ov]overlay=0:0:format=auto:shortest=0,"
              f"format=yuv420p[vo]")
    final_v = "[vo]"
fade_out = cfg.get("fade_out", 0.8)
fc.append(f"{final_v}fade=t=out:st={total - fade_out:.3f}:d={fade_out}[v]")
fc.append(f"[1:a]aresample={SR},atrim=0:{total:.3f},volume='{expr}':eval=frame,volume={mus_gain}dB[m]")
fc.append(f"[0:a][m]amix=inputs=2:normalize=0:duration=first,"
          f"acompressor=threshold=-14dB:ratio=2.5:attack=10:release=200,"
          f"afade=t=out:st={total - fade_out - 0.4:.3f}:d={fade_out + 0.4},"
          f"loudnorm=I=-14:TP=-1.5:LRA=9[a]")
run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
     "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
     "-c:v", "libx264", "-preset", "veryfast" if draft else "slow", "-crf", "26" if draft else "17",
     "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p", "-r", str(FPS),
     "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", str(out)])
(out.with_suffix(".spans.json")).write_text(json.dumps({"total": total, "voice": voice_spans}))
print("wrote", out)
