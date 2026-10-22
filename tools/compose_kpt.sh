#!/usr/bin/env bash
# Final composite for the KPT reel: footage layer + transparent motion-graphics frames +
# audio mix, with a short decaying camera shake on the big hits, loudness-normalised for
# social (-14 LUFS, peak-limited).
#
# The audio is normalised and encoded in its own pass and then stream-copied into the MP4:
# running loudnorm (3 s lookahead) inside the same filter graph as the PNG-sequence overlay
# dropped most audio packets (2.9 s holes every 3 s).
#
# Usage: tools/compose_kpt.sh FOOTAGE.mp4 OVERLAY_DIR MIX.wav OUT.mp4
set -euo pipefail
footage=$1 ovdir=$2 mix=$3 out=$4
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# 0) Chromium writes fully opaque frames as RGB PNGs; a pixel-format change mid-sequence
#    makes ffmpeg re-initialise the filter graph and drop/duplicate frames, so force RGBA
for f in "$ovdir"/f*.png; do
  if [ "$(ffprobe -v error -show_entries stream=pix_fmt -of csv=p=0 "$f")" != "rgba" ]; then
    ffmpeg -v error -y -i "$f" -pix_fmt rgba "$tmp/fix.png" && mv "$tmp/fix.png" "$f"
  fi
done

# 1) audio: normalise, limit, encode
ffmpeg -v error -y -i "$mix" \
  -af "loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000,alimiter=limit=0.79:attack=1:release=50:level=false" \
  -t 30 -c:a aac -b:a 192k -ar 48000 "$tmp/audio.m4a"

# shake amplitude (px): decays after each hit
amp="14*exp(-(t-0.55)*9)*between(t,0.55,1.0)+12*exp(-(t-9.0)*9)*between(t,9.0,9.45)"
amp="$amp+16*exp(-(t-17.0)*9)*between(t,17.0,17.45)+20*exp(-(t-21.0)*8)*between(t,21.0,21.5)"
win="between(t,0.55,1.0)+between(t,9.0,9.45)+between(t,17.0,17.45)+between(t,21.0,21.5)"

# 2) video: overlay + shake, then mux with the encoded audio
ffmpeg -v error -y -i "$footage" -framerate 30 -i "$ovdir/f%04d.png" -i "$tmp/audio.m4a" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p,split[a][b];
    [b]scale=1112:1978:flags=lanczos,crop=1080:1920:x='16+($amp)*sin(t*83)':y='29+($amp)*cos(t*71)'[s];
    [a][s]overlay=0:0:enable='$win'[v]" \
  -map "[v]" -map 2:a -frames:v 900 -r 30 \
  -c:v libx264 -preset slow -crf 16 -profile:v high -pix_fmt yuv420p \
  -c:a copy -movflags +faststart "$out"

# 3) sanity check: 900 video frames; 30 s of AAC at 48 kHz is ~1406 packets with no holes
pk=$(ffprobe -v error -select_streams a -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$out")
gap=$(ffprobe -v error -select_streams a -show_entries packet=pts_time -of csv=p=0 "$out" |
      awk -F, 'NR>1 && $1-p>0.03 {g++} {p=$1} END {print g+0}')
nf=$(ffprobe -v error -select_streams v -count_frames -show_entries stream=nb_read_frames -of csv=p=0 "$out")
if [ "$pk" -lt 1390 ] || [ "$gap" -ne 0 ] || [ "$nf" -ne 900 ]; then
  echo "check failed: $nf video frames, $pk audio packets, $gap audio gaps" >&2; exit 1
fi
echo "wrote $out ($nf frames; audio: $pk packets, no gaps)"
