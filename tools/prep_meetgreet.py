"""Build the derived source assets for the Meet & Greet reel (run before reel_edit.py).

Usage: python3 prep_meetgreet.py MEDIA_DIR

Writes into MEDIA_DIR:
  15_tight.mov   "Mungkin terdetik daripada itulah saya menulis buku ini." with the
                 filler ("eh" + 0.5 s pause after "Mungkin", "ah" before "saya") cut out.
                 Audio is spliced word-tight with 12 ms crossfades. Picture: an audience
                 cutaway covers "Mungkin" and the first splice (L-cut), then the speaker in
                 sync, then a punch-in on the second splice so the jump cut reads as intended.
  58_cover_center.jpg  the whole book cover centred in a 1080x1920 frame over a blurred
                 copy of the same shot (the source frame has the book on the left edge).
"""
import subprocess
import sys
from pathlib import Path

W, H, FPS, SR = 1080, 1920, 30, 48000
media = Path(sys.argv[1] if len(sys.argv) > 1 else "media")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ffmpeg failed:\n{' '.join(map(str, cmd))}\n{r.stderr[-2500:]}")


# --- clip 15: word-tight splice -------------------------------------------------------
# kept speech chunks (source seconds), found with Whisper large-v3 (filler-aware prompt)
# and checked against the energy envelope / spectrogram (/s/ of "saya" at 3.75 s)
CHUNKS = [(1.33, 1.55),   # Mungkin
          (2.07, 3.55),   # terdetik daripada itulah
          (3.745, 5.26)]  # saya menulis buku ini.
XF = 0.012
src15 = media / "15.mp4"
a_parts, labels = [], []
for k, (a, b) in enumerate(CHUNKS):
    a_parts.append(f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample={SR}[a{k}]")
    labels.append(f"[a{k}]")
afc = ";".join(a_parts) + ";"
afc += f"[a0][a1]acrossfade=d={XF}:c1=tri:c2=tri[x01];[x01][a2]acrossfade=d={XF}:c1=tri:c2=tri[aout]"
dur_total = sum(b - a for a, b in CHUNKS) - 2 * XF

# picture plan (output-relative): cutaway 07 for the first 0.9 s, then 15 in sync.
cut_len = 0.90
b_sync_in = CHUNKS[1][0] + (cut_len - (CHUNKS[0][1] - CHUNKS[0][0]))   # where chunk B is at t=0.9
v1_len = (CHUNKS[1][1] - CHUNKS[1][0]) - (cut_len - (CHUNKS[0][1] - CHUNKS[0][0])) - XF
v2_len = dur_total - cut_len - v1_len


def framing(z, fx, fy):
    # cover-fit to 9:16 then a static punch-in of z around (fx, fy)
    cw, ch = f"{W}/{z}", f"{H}/{z}"
    return (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},"
            f"crop='{cw}':'{ch}':'min(max(0,{fx}*iw-{cw}/2),iw-{cw})':'min(max(0,{fy}*ih-{ch}/2),ih-{ch})',"
            f"scale={W}:{H}:flags=lanczos,setsar=1,fps={FPS},format=yuv420p")


vfc = (f"[1:v]trim=1.0:{1.0 + cut_len},setpts=PTS-STARTPTS,{framing(1.08, 0.5, 0.55)}[v0];"
       f"[0:v]trim={b_sync_in:.3f}:{b_sync_in + v1_len:.3f},setpts=PTS-STARTPTS,{framing(1.38, 0.45, 0.50)}[v1];"
       f"[0:v]trim={CHUNKS[2][0]:.3f}:{CHUNKS[2][0] + v2_len + 0.05:.3f},setpts=PTS-STARTPTS,"
       f"{framing(1.62, 0.45, 0.46)}[v2];[v0][v1][v2]concat=n=3:v=1:a=0[vout]")
run(["ffmpeg", "-v", "error", "-y", "-i", str(src15), "-i", str(media / "07.mp4"),
     "-filter_complex", afc + ";" + vfc, "-map", "[vout]", "-map", "[aout]", "-t", f"{dur_total:.3f}",
     "-c:v", "libx264", "-crf", "10", "-preset", "slow", "-c:a", "pcm_s16le", str(media / "15_tight.mov")])
print(f"15_tight.mov: {dur_total:.3f}s  (cutaway {cut_len}s, sync {v1_len:.3f}s, punch-in {v2_len:.3f}s)")

# --- book cover centred ---------------------------------------------------------------
# frame 58 @ 10.25 s shows the whole cover; book box in that frame ~ x 0.02-0.80, y 0.28-0.87
CX0, CX1, CY0, CY1 = 0.00, 0.82, 0.225, 0.925          # crop symmetric around the book
bw = 1000                                              # placed width in the 1080 frame
fc = (f"[0:v]split[a][b];"
      f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},gblur=sigma=38,"
      f"eq=brightness=-0.10:saturation=0.85[bg];"
      f"[b]crop=iw*{CX1 - CX0}:ih*{CY1 - CY0}:iw*{CX0}:ih*{CY0},scale={bw}:-2:flags=lanczos,format=rgba,"
      # feather the crop edge so it melts into the blurred plate
      f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':"
      f"a='255*min(1,min(min(X,W-1-X),min(Y,H-1-Y))/34)'[fg];"
      f"[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuvj420p")
run(["ffmpeg", "-v", "error", "-y", "-ss", "10.25", "-i", str(media / "58.mp4"), "-frames:v", "1",
     "-filter_complex", fc, "-q:v", "1", str(media / "58_cover_center.jpg")])
print("58_cover_center.jpg written")
