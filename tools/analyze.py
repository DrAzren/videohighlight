"""Probe every video in a folder and build contact sheets + loudness maps so the best
moments can be picked by eye.

Usage: python3 analyze.py SRC_DIR OUT_DIR
Writes OUT_DIR/index.json and OUT_DIR/sheets/<n>.jpg (one frame every STEP seconds,
timestamped).
"""
import json
import subprocess
import sys
from pathlib import Path

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".3gp", ".webm", ".mts"}
STEP = 2.0

src, out = Path(sys.argv[1]), Path(sys.argv[2])
(out / "sheets").mkdir(parents=True, exist_ok=True)


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                        "-show_format", str(p)], capture_output=True, text=True)
    j = json.loads(r.stdout or "{}")
    v = next((s for s in j.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in j.get("streams", []) if s["codec_type"] == "audio"), None)
    if not v:
        return None
    w, h = int(v["width"]), int(v["height"])
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"])
    rot = int(v.get("tags", {}).get("rotate", rot))
    if abs(rot) % 180 == 90:
        w, h = h, w
    return {"width": w, "height": h, "duration": float(j["format"].get("duration", 0)),
            "has_audio": a is not None, "fps": v.get("avg_frame_rate")}


def loudness(p, dur):
    """Per-second RMS level in dB (speech / applause detection)."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(p), "-vn", "-ac", "1", "-ar", "8000",
                        "-f", "s16le", "-"], capture_output=True)
    import numpy as np
    x = np.frombuffer(r.stdout, dtype=np.int16).astype(float) / 32768
    per = []
    for i in range(int(dur) + 1):
        seg = x[i * 8000:(i + 1) * 8000]
        per.append(round(float(20 * np.log10(np.sqrt((seg ** 2).mean()) + 1e-9)), 1) if len(seg) else -90)
    return per


files = sorted(p for p in src.rglob("*") if p.suffix.lower() in VIDEO_EXT and not p.name.startswith("._"))
index = []
for n, p in enumerate(files, 1):
    info = probe(p)
    if not info:
        continue
    info.update(id=n, path=str(p), name=p.name)
    if info["has_audio"]:
        info["loud_db"] = loudness(p, info["duration"])
    cols = 6
    frames = max(1, int(info["duration"] // STEP))
    rows = min(8, -(-frames // cols))
    step = max(STEP, info["duration"] / (cols * rows))
    info["sheet_step"] = step
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-i", str(p), "-vf",
        f"fps=1/{step},scale=320:-2,drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='#{n} %{{pts\\:hms}}':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.6,"
        f"tile={cols}x{rows}:padding=4",
        "-frames:v", "1", "-q:v", "4", str(out / "sheets" / f"{n:02d}.jpg")], check=False)
    index.append(info)
    print(f"#{n:02d} {p.name}  {info['width']}x{info['height']}  {info['duration']:.1f}s  step={step:.1f}")

(out / "index.json").write_text(json.dumps(index, indent=1))
print(f"{len(index)} videos, total {sum(i['duration'] for i in index)/60:.1f} min")
