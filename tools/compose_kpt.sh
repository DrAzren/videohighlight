#!/usr/bin/env bash
# Final composite for the KPT reel: footage layer + transparent motion-graphics frames +
# audio mix, with a short decaying camera shake on the big hits, loudness-normalised for
# social (-14 LUFS, -1.5 dBTP).
#
# Usage: tools/compose_kpt.sh FOOTAGE.mp4 OVERLAY_DIR MIX.wav OUT.mp4
set -euo pipefail
footage=$1 ovdir=$2 mix=$3 out=$4

# shake amplitude (px): decays after each hit
amp="14*exp(-(t-0.55)*9)*between(t,0.55,1.0)+12*exp(-(t-9.0)*9)*between(t,9.0,9.45)"
amp="$amp+16*exp(-(t-17.0)*9)*between(t,17.0,17.45)+20*exp(-(t-21.0)*8)*between(t,21.0,21.5)"
win="between(t,0.55,1.0)+between(t,9.0,9.45)+between(t,17.0,17.45)+between(t,21.0,21.5)"

ffmpeg -v error -y -i "$footage" -framerate 30 -i "$ovdir/f%04d.png" -i "$mix" \
  -filter_complex "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p,split[a][b];
    [b]scale=1112:1978:flags=lanczos,crop=1080:1920:x='16+($amp)*sin(t*83)':y='29+($amp)*cos(t*71)'[s];
    [a][s]overlay=0:0:enable='$win'[v];
    [2:a]loudnorm=I=-14:TP=-1.5:LRA=9,aresample=48000,alimiter=limit=0.79:attack=1:release=50:level=false[au]" \
  -map "[v]" -map "[au]" -t 30 -r 30 \
  -c:v libx264 -preset slow -crf 16 -profile:v high -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$out"
echo "wrote $out"
