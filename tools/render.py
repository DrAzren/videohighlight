"""Render a vertical 9:16 highlight reel from a cut list.

Usage: python3 render.py cuts.json OUT.mp4

cuts.json:
{
  "music": "work/music.wav",
  "xfade": 0.35,
  "segments": [
    {"src": "path.mp4", "start": 12.0, "dur": 3.0,
     "mode": "fill" | "crop",      # fill = blurred background + full frame; crop = fill 9:16
     "cx": 0.5,                    # crop centre (0..1) when mode=crop
     "zoom": 1.08,                 # slow push-in amount over the clip
     "text": "Setiap langkah\\nbermula dengan niat",
     "voice": false}               # keep original audio (music ducks under it)
  ]
}
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/opentype/montserrat/Montserrat-ExtraBold.otf"

cfg = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
tmp = Path(tempfile.mkdtemp(prefix="reel_"))
GRAD = tmp / "grad.png"
# bottom-up dark gradient so captions stay readable on busy backgrounds
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}",
                "-vf", "format=rgba,geq=r=0:g=0:b=0:a='if(gt(Y,H*0.45),200*pow((Y-H*0.45)/(H*0.55),1.4),0)'",
                "-frames:v", "1", str(GRAD)], check=True)
XF = float(cfg.get("xfade", 0.35))
segs = cfg["segments"]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-3000:]}")


def video_filter(s):
    dur, zoom = s["dur"], s.get("zoom", 1.06)
    # slow Ken-Burns push-in: scale grows linearly from 1 to `zoom` over the clip
    z = f"(1+({zoom}-1)*t/{dur})"
    if s.get("mode", "fill") == "crop":
        cx = s.get("cx", 0.5)
        # stabilise (vidstab, 2-pass) -> clean up noise -> cover-scale to 9:16 around cx
        # -> slow push-in -> sharpen -> cinematic grade
        stab = ""
        if s.get("stab", True):
            trf = tmp / f"stab{id(s)}.trf"
            run(["ffmpeg", "-v", "error", "-y", "-ss", str(s["start"]), "-t", str(dur),
                 "-i", s["src"], "-vf", f"vidstabdetect=shakiness=6:accuracy=12:result={trf}",
                 "-f", "null", "-"])
            stab = (f"vidstabtransform=input={trf}:smoothing=18:optzoom=1:"
                    f"interpol=bicubic:crop=black,")
        fg = (f"{stab}fps={FPS},hqdn3d=2:1.5:4:3,"
              f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
              f"crop={W}:{H}:(iw-{W})*{cx}:(ih-{H})/2,"
              f"scale=w='{W}*{z}':h='{H}*{z}':eval=frame:flags=lanczos,"
              f"crop={W}:{H}")
        grade = ("cas=strength=0.5,eq=contrast=1.07:saturation=1.16:gamma=1.04:brightness=0.01,"
                 "colorbalance=rs=0.02:bs=-0.03:rm=0.03:bm=-0.03:rh=0.02:bh=-0.02,"
                 "vignette=angle=PI/7")
        chain = f"[0:v]{fg},setsar=1,{grade}[v0]"
        if s.get("text"):
            chain = (f"[0:v]{fg},setsar=1,{grade}[g0];movie={GRAD}[gr];"
                     f"[g0][gr]overlay=0:0[v0]")
    else:
        chain = (
            f"[0:v]split[a][b];"
            f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=30:3,eq=brightness=-0.12:saturation=1.1[bg];"
            f"[b]scale={W}*1.0:-2:flags=lanczos,"
            f"scale=w='iw*{z}':h='ih*{z}':eval=frame,crop='min(iw,{W})':'ih'[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2-80,setsar=1,fps={FPS}[v0]")
    last = "v0"
    if s.get("text"):
        tf = tmp / f"t{id(s)}.txt"
        tf.write_text(s["text"])
        t_in, t_out = 0.25, dur - 0.25
        alpha = (f"if(lt(t,{t_in}),0,if(lt(t,{t_in}+0.4),(t-{t_in})/0.4,"
                 f"if(lt(t,{t_out}-0.35),1,if(lt(t,{t_out}),({t_out}-t)/0.35,0))))")
        y = s.get("text_y", "h*0.72-text_h/2")
        longest = max(len(l) for l in s["text"].split("\n"))
        size = s.get("size", int(min(84, 940 / (0.66 * longest))))
        chain += (f";[{last}]drawtext=fontfile={FONT}:textfile={tf}:fontsize={size}:"
                  f"fontcolor=white:line_spacing=20:text_align=C:x=(w-text_w)/2:y={y}:"
                  f"shadowcolor=black@0.75:shadowx=0:shadowy=4:borderw=3:bordercolor=black@0.35:"
                  f"alpha='{alpha}'[v1]")
        last = "v1"
    return chain, last


clips = []
for i, s in enumerate(segs):
    vf, last = video_filter(s)
    o = tmp / f"s{i:02d}.mp4"
    vol = s.get("voice_gain", 1.0) if s.get("voice") else 0.0
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", str(s["start"]), "-t", str(s["dur"]),
           "-i", s["src"], "-f", "lavfi", "-t", str(s["dur"]), "-i",
           "anullsrc=r=48000:cl=stereo",
           "-filter_complex",
           vf + f";[0:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},"
                f"apad,atrim=0:{s['dur']}[a0]",
           "-map", f"[{last}]", "-map", "[a0]",
           "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p",
           "-c:a", "pcm_s16le", "-t", str(s["dur"]), str(o)]
    # sources without audio: use the silent track instead
    has_audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                                "stream=index", "-of", "csv=p=0", s["src"]],
                               capture_output=True, text=True).stdout.strip()
    if not has_audio:
        cmd[cmd.index("-filter_complex") + 1] = vf + f";[1:a]anull[a0]"
    run(cmd)
    clips.append(o)
    print(f"segment {i+1}/{len(segs)} done")

# join with crossfades
inputs, fc = [], []
for c in clips:
    inputs += ["-i", str(c)]
offset, vprev, aprev = 0.0, "0:v", "0:a"
for i in range(1, len(clips)):
    offset += segs[i - 1]["dur"] - XF
    trans = segs[i].get("transition", "fade")
    fc.append(f"[{vprev}][{i}:v]xfade=transition={trans}:duration={XF}:offset={offset:.3f}[vx{i}]")
    fc.append(f"[{aprev}][{i}:a]acrossfade=d={XF}[ax{i}]")
    vprev, aprev = f"vx{i}", f"ax{i}"
total = sum(s["dur"] for s in segs) - XF * (len(segs) - 1)

# music with ducking under voice segments
duck, t = [], 0.0
for i, s in enumerate(segs):
    if s.get("voice"):
        duck.append(f"between(t,{t:.2f},{t + s['dur']:.2f})")
    t += s["dur"] - XF
duck_expr = "+".join(duck) or "0"
music_i = len(clips)
inputs += ["-i", cfg["music"]]
fade_v = f"fade=t=out:st={total - 0.8:.2f}:d=0.8"
fc.append(f"[{vprev}]{fade_v},format=yuv420p[vout]")
fc.append(f"[{music_i}:a]atrim=0:{total:.2f},volume='if({duck_expr},0.22,0.9)':eval=frame,"
          f"afade=t=out:st={total - 2:.2f}:d=2[m]")
fc.append(f"[{aprev}][m]amix=inputs=2:normalize=0,alimiter=limit=0.95,"
          f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]")

run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fc),
     "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
     "-profile:v", "high", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
     "-ar", "48000", "-movflags", "+faststart", "-t", f"{total:.2f}", str(out)])
print(f"wrote {out} ({total:.1f}s)")
