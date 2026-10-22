# Mental Health @ KPT — 30 s highlight reel (15 Oktober 2026)

Output: `out/KPT_MentalHealth_Reel_30s.mp4`, 1080×1920, 30 fps, 30.0 s (900 frames), H.264 + AAC 48 kHz,
−13.6 LUFS integrated, −1.6 dBTP. Source footage is native 1080×1920, so it is delivered at 1080p (no 4K upscale).

Source: Google Photos shared album (24 vertical videos + 2 photos). The parking-sign photo was left out
because it shows a car registration plate.

## Timeline (120 BPM, cuts on the beat)

| Time | Shot (file @ s) | Graphics |
|---|---|---|
| 0.0–1.5 | 13 @ 16.9 Dr Azren on mic, turning to camera (punch-in) | flash, burst + confetti, **MENTAL HEALTH @ KPT!** |
| 1.5–3.0 | 13 @ 0.4 students laughing (whip) | **15 OKTOBER 2026** paper strip |
| 3.0–5.0 | 04 @ 0.1 "Saringan Kesihatan Mental" banner | navy paper-rip reveal, **MENTAL HEALTH BOOTH**, wellbeing icon stickers |
| 5.0–7.0 | 04 @ 6.9 booth team with visitor (whip) | **SCREENING • AWARENESS • SUPPORT** chips |
| 7.0–9.0 | 04 @ 14.4 visitor smiling, holding a booth item (punch) | shutter flash, sparkles |
| 9.0–10.5 | 08 @ 0.3 "Mengurus Overthinking" title screen | iris transition, **LET'S TALK about MENTAL HEALTH** |
| 10.5–12.0 | 10 @ 0.4 packed hall (whip) | |
| 12.0–14.0 | 20 @ 16.6 Dr Azren on stage — **original audio** 17.35–18.55 s | lower-third, karaoke subtitle "Kita validate emosi kita." |
| 14.0–15.5 | 12 @ 5.6 audience (whip) | doodles, **Learn • Connect • Empower** |
| 15.5–17.0 | 19 @ 3.6 stage talk, freeze at 16.5 | freeze-frame cut-out (Higgsfield background removal) |
| 17.0–18.0 | 13 @ 13.2 mic handed to a smiling audience member | cream paper-rip, film-strip sprockets, doodles |
| 18.0–19.0 | 13 @ 24.4 hands raised (whip) | |
| 19.0–20.5 | split: 08 @ 6.3 clapping / 15 @ 6.5 smiling audience | **SMALL CONVERSATIONS.** on the divider |
| 20.5–21.5 | 24 @ 0.4 talk, freeze at 21.0 | freeze-frame cut-out, **BIG IMPACT.** slam + shake |
| 21.5–22.5 | 16 @ 3.4 Q&A with a participant (whip) | |
| 22.5–24.0 | 15 @ 0.2 booth team member with mic | polaroid collage (04 @ 8.5, 11 @ 0.3, 26 @ 0.8) |
| 24.0–27.0 | 21 @ 0.3 appreciation presentation (0.9× speed) | **Terima Kasih, Kementerian Pendidikan Tinggi!** |
| 27.0–30.0 | photo 23: group selfie, 2.5D pan audience → Dr Azren | **Dr Fakrul Azren / Spread Positivity**, gold particles, fade |

## Speech excerpt

Transcribed with Whisper large-v3 (Malay). The line is from file 20 (stage talk):
"…Sebab tu simptom lah, **kita validate emosi kita**." The excerpt keeps only the complete phrase
"Kita validate emosi kita" (17.35–18.55 s); the in-point was chosen by re-transcribing candidate cuts with
context so no fragment of the preceding word remains. Music is ducked and low-passed under it.

## Rebuild

```
python3 tools/analyze.py work/src work/ana                      # contact sheets
python3 tools/render_v4.py reels/kpt_cuts.json work/footage.mp4 work/seg
python3 tools/make_kpt_music.py work/kpt_music.wav               # needs numpy + scipy
python3 tools/mix_kpt_audio.py work/kpt_music.wav work/src/20_2026-10-15_161040.mp4 work/kpt_mix.wav
# overlay: freeze frames come from work/seg/s09.mp4 (frame 44) and s13.mp4 (frame 29); cut-outs via Higgsfield
sed "s#FONTS/#../fonts/#g" tools/overlay/kpt.html > work/overlay/index.html   # assets in work/overlay/assets
python3 -m http.server 8765 --bind 127.0.0.1 &   # from work/
node tools/render_overlay.mjs http://127.0.0.1:8765/overlay/index.html work/ovframes 30 30 4
tools/compose_kpt.sh work/footage.mp4 work/ovframes work/kpt_mix.wav out/KPT_MentalHealth_Reel_30s.mp4
```

Fonts (Google Fonts, latin subset): Anton, Bebas Neue, Montserrat, Playfair Display, Caveat → `work/fonts/`.
