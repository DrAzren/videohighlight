"""Cut the exact source spans an edit list uses, ready for an external upscaler
(Higgsfield / Topaz 2160p 9:16).

Usage: python3 upscale_prep.py EDL.json SRC_DIR OUT_DIR [--only K,K,...]

For every video segment k: trims [in - 0.2, in + span + 0.3] (span accounts for
speed / ramp and the transition handle) to OUT_DIR/in_KK.mp4 at the native frame
rate (60 fps slow motion survives), x264 CRF 12, no audio. Truly landscape sources
are cropped to 9:16 around the segment's cx first; phone clips stored as 1920x1080
with a 90-degree rotation flag are portrait and are NOT cropped (ffmpeg auto-rotates).
Writes OUT_DIR/manifest.json with the trim offsets so the edit list can be pointed at
the upscaled files (in := in - a).
"""
import json
import subprocess
import sys
from pathlib import Path

edl = json.loads(Path(sys.argv[1]).read_text())
SRC, OUT = Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
only = {int(k) for k in sys.argv[sys.argv.index("--only") + 1].split(",")} if "--only" in sys.argv else None


def display_size(path):
    st = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                                    "stream=width,height,r_frame_rate:stream_side_data=rotation", "-of", "json",
                                    str(path)], capture_output=True, text=True).stdout)["streams"][0]
    rot = next((abs(int(d.get("rotation", 0))) for d in st.get("side_data_list", []) if "rotation" in d), 0)
    w, h = (st["height"], st["width"]) if rot % 180 == 90 else (st["width"], st["height"])
    return w, h, st["r_frame_rate"]


manifest = []
for k, s in enumerate(edl["segments"]):
    src = s.get("orig", s)["src"]
    if not src.endswith(".mp4") or (only and k not in only):
        continue
    start = s.get("orig", s)["in"]
    total = s["dur"] + 0.8
    span = (s["ramp"][0] + s["ramp"][1]) / 2 * total if "ramp" in s else total * s.get("speed", 1.0)
    a, b = max(0.0, start - 0.2), start + span + 0.3
    w, h, fps = display_size(SRC / src)
    vf = "format=yuv420p"
    if w > h:
        cw = int(h * 9 / 16) // 2 * 2
        vf = f"crop={cw}:{h}:{w}*{s.get('cx', 0.5)}-{cw // 2}:0," + vf
    out = OUT / f"in_{k:02d}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(SRC / src),
                    "-vf", vf, "-c:v", "libx264", "-crf", "12", "-preset", "slow", "-an", str(out)], check=True)
    manifest.append({"k": k, "src": src, "in": start, "a": a, "b": b, "fps": fps, "landscape": w > h,
                     "file": out.name})
    print(k, src, f"{a:.2f}-{b:.2f}", f"{w}x{h}", fps, "crop" if w > h else "", flush=True)
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
