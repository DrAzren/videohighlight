"""Lock a handheld shot to a virtual tripod.

Usage: python3 lock_shot.py SRC START DUR OUT.mp4 [CX]

Every frame is aligned to the middle frame (ORB features + RANSAC similarity
transform, so people moving in the scene do not drag the background), then the
largest 9:16 window that stays inside every warped frame is cut out around CX
(0..1, default 0.5) and written at the source frame rate. The camera move is
removed rather than smoothed; the result looks like it was shot on a tripod.
"""
import subprocess
import sys

import cv2
import numpy as np

src, start, dur, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
cx = float(sys.argv[5]) if len(sys.argv) > 5 else 0.5

probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                        "stream=r_frame_rate", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
fps = probe.splitlines()[0].strip(",")
r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(dur), "-i", src,
                    "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True)
w, h = 1080, 1920
frames = np.frombuffer(r.stdout, np.uint8).reshape(-1, h, w, 3)
ref = frames[len(frames) // 2]
orb = cv2.ORB_create(4000)
gray = lambda f: cv2.cvtColor(cv2.resize(f, (w // 2, h // 2)), cv2.COLOR_BGR2GRAY)
kr, dr = orb.detectAndCompute(gray(ref), None)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
mats, corners = [], []
for f in frames:
    k, d = orb.detectAndCompute(gray(f), None)
    m = sorted(bf.match(d, dr), key=lambda x: x.distance)[:800]
    p = np.float32([k[x.queryIdx].pt for x in m]) * 2
    q = np.float32([kr[x.trainIdx].pt for x in m]) * 2
    M, _ = cv2.estimateAffinePartial2D(p, q, method=cv2.RANSAC, ransacReprojThreshold=3.0)
    mats.append(M)
    c = cv2.transform(np.float32([[[0, 0], [w, 0], [w, h], [0, h]]]), M)[0]
    corners.append(c)
# inner box valid in every frame (conservative: axis-aligned bounds of warped corners)
x0 = max(max(c[0, 0], c[3, 0]) for c in corners)
x1 = min(min(c[1, 0], c[2, 0]) for c in corners)
y0 = max(max(c[0, 1], c[1, 1]) for c in corners)
y1 = min(min(c[2, 1], c[3, 1]) for c in corners)
bw, bh = x1 - x0, y1 - y0
cw = min(bw, bh * 9 / 16)
ch = cw * 16 / 9
left = min(max(x0 + cx * bw - cw / 2, x0), x1 - cw)
top = y0 + (bh - ch) / 2
ow, oh = int(cw) // 2 * 2, int(ch) // 2 * 2
print(f"{len(frames)} frames, travel box {bw:.0f}x{bh:.0f}, crop {ow}x{oh} at ({left:.0f},{top:.0f})")
enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{ow}x{oh}",
                        "-r", fps, "-i", "-", "-c:v", "libx264", "-crf", "10", "-preset", "slow",
                        "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
T = np.float32([[1, 0, -left], [0, 1, -top]])
for f, M in zip(frames, mats):
    A = np.vstack([M, [0, 0, 1]])
    B = np.vstack([T, [0, 0, 1]]) @ A
    enc.stdin.write(cv2.warpAffine(f, B[:2], (ow, oh), flags=cv2.INTER_CUBIC).tobytes())
enc.stdin.close()
enc.wait()
