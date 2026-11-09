"""Write the HyperFrames overlay project (titles, ink underline, Malay captions) for the
Meet & Greet reel. The overlay renders with a transparent background and is composited
over the ffmpeg edit by reel_edit.py.

Usage: python3 make_overlay.py OUT_DIR
Then:  cd OUT_DIR && npx hyperframes check && npx hyperframes render --format mov -o overlay.mov

All times are film seconds and must match reels/meetgreet_cuts.json.
Word times come from Whisper (medium + large-v3 cross-check) and were checked by ear-proxy
(energy envelope) on every caption; spelling was corrected by hand.
"""
import html
import sys
from pathlib import Path

out = Path(sys.argv[1] if len(sys.argv) > 1 else "overlay")
(out / "compositions").mkdir(parents=True, exist_ok=True)

TOTAL = 51.35
YELLOW = "#FFD21F"   # the book cover's yellow
NAVY = "#1B2A4A"

# Caption groups: (id, start, end, kicker, lines[[(word, t_spoken, accent)]], style)
# Each line is a list of words; t_spoken is when the word is said (karaoke fill).
CAPTIONS = [
    ("cap-hook1", 0.0, 3.0, None, [
        [("Benda", 0.22), ("pertama", 0.36), ("yang", 0.74), ("kita", 0.90)],
        [("buat", 1.22), ("bila", 1.56), ("bangun", 1.84), ("pagi,", 2.12)]], "hook"),
    ("cap-hook2", 3.04, 4.42, None, [
        [("bukan", 3.14)], [("scroll", 3.54, True), ("telefon.", 3.86, True)]], "hook-big"),
    ("cap-mitos", 10.45, 13.85, None, [
        [("Mitos-mitos", 10.60), ("begini", 11.35)],
        [("sebenarnya", 11.95), ("menyakitkan.", 12.42, True)]], "talk"),
    ("cap-q", 16.85, 19.45, "Soalan audiens", [
        [("Macam", 16.90), ("mana", 17.20), ("kami", 17.40)],
        [("nak", 17.65), ("bantu", 18.45), ("mereka?", 18.75)]], "talk"),
    ("cap-a", 19.52, 22.16, "Jawapan Dr Azren", [
        [("…untuk", 19.57), ("mereka", 19.85), ("dapatkan", 20.21)],
        [("bantuan", 20.93, True), ("yang", 21.33), ("sepatutnya", 21.45, True), ("lah.", 21.89)]], "talk talk-sm"),
    ("cap-buku1", 22.21, 24.55, None, [
        [("Mungkin", 22.25), ("terdetik", 22.97)],
        [("daripada", 23.61), ("itulah", 23.99)]], "talk"),
    ("cap-buku2", 24.55, 26.33, None, [
        [("saya", 24.64), ("menulis", 24.99)],
        [("buku", 25.44, True), ("ini.", 25.84, True)]], "talk"),
]

# scene windows (film time)
TITLE = (4.35, 6.0)      # location title: 4.35 -> 10.35
CLOSE = (41.35, 5.0)     # thank-you line over the group shot


def word_spans(lines, gid):
    rows = []
    k = 0
    for line in lines:
        spans = []
        for w in line:
            text, accent = w[0], (len(w) > 2 and w[2])
            spans.append(f'<span id="{gid}-w{k}" class="w{" acc" if accent else ""}">'
                         f'{html.escape(text)}</span>')
            k += 1
        rows.append('<span class="ln">' + " ".join(spans) + "</span>")
    return "".join(rows)


# ---------------- captions scene (0 -> 26.4) ----------------
cap_end = TOTAL  # captions host spans the film; groups only exist 0-26.4 s
cap_html, cap_js = [], []
for gid, a, b, kicker, lines, style in CAPTIONS:
    kick = f'<span class="kick">{html.escape(kicker)}</span>' if kicker else ""
    cap_html.append(
        f'<div id="{gid}" class="grp {style} clip" data-start="{a:.2f}" data-duration="{b - a:.2f}">'
        f'{kick}<div class="pill">{word_spans(lines, gid)}</div></div>')
    words = [w for line in lines for w in line]
    # group arrives as one blurred line (0.16 s); words not yet spoken sit at 62 % white,
    # each word fills to full white (accent words to book-yellow) exactly when it is said.
    enter = max(a, 0.0)
    if a > 0:
        cap_js.append(f'tl.fromTo("#{gid}", {{opacity:0, y:14, filter:"blur(6px)"}}, '
                      f'{{opacity:1, y:0, filter:"blur(0px)", duration:0.18, ease:"power3.out"}}, {enter:.2f});')
    else:
        cap_js.append(f'tl.set("#{gid}", {{opacity:1}}, 0);')
    for k, w in enumerate(words):
        t = w[1]
        acc = len(w) > 2 and w[2]
        cap_js.append(f'tl.fromTo("#{gid}-w{k}", {{opacity:0.62, color:"#FFFFFF"}}, '
                      f'{{opacity:1, color:"{YELLOW if acc else "#FFFFFF"}", duration:0.12, ease:"none"}}, {t:.2f});')
        if not acc:
            cap_js.append(f'tl.fromTo("#{gid}-w{k}", {{scale:1.0}}, {{scale:1.03, duration:0.08, ease:"power2.out", '
                          f'yoyo:true, repeat:1}}, {t:.2f});')
        else:
            cap_js.append(f'tl.fromTo("#{gid}-w{k}", {{scale:1.0}}, {{scale:1.05, duration:0.12, ease:"back.out(2)", '
                          f'yoyo:true, repeat:1}}, {t:.2f});')
    cap_js.append(f'tl.to("#{gid}", {{opacity:0, filter:"blur(6px)", duration:0.14, ease:"power2.in"}}, {b - 0.14:.2f});')
    cap_js.append(f'tl.set("#{gid}", {{opacity:0}}, {b:.2f});')

captions = f"""<template>
<style>
  #captions {{ position:absolute; inset:0; }}
  #captions .grp {{ position:absolute; left:56px; right:136px; bottom:600px; display:flex; flex-direction:column;
    align-items:center; text-align:center; opacity:0; overflow:visible; }}
  #captions .pill {{ display:inline-flex; flex-direction:column; align-items:center; gap:2px; padding:18px 30px 20px;
    border-radius:26px; background:rgba(10,14,28,0.56); backdrop-filter:blur(6px); }}
  #captions .ln {{ display:block; white-space:nowrap; font-family:'Montserrat',sans-serif; font-weight:800;
    font-size:58px; line-height:1.14; letter-spacing:-0.01em; word-spacing:0.14em; color:#fff;
    text-shadow:0 2px 10px rgba(0,0,0,0.55), 0 1px 2px rgba(0,0,0,0.6); }}
  #captions .w {{ display:inline-block; transform-origin:50% 70%; }}
  #captions .hook .ln {{ font-size:58px; }}
  #captions .talk-sm .ln {{ font-size:50px; }}
  #captions .hook-big .ln {{ font-size:82px; font-weight:900; line-height:1.04; }}
  #captions .hook-big .ln:first-child {{ font-size:54px; font-weight:800; }}
  #captions .kick {{ margin-bottom:12px; padding:8px 18px 9px; border-radius:999px; background:{YELLOW};
    color:{NAVY}; font-family:'Inter',sans-serif; font-weight:900; font-size:28px; letter-spacing:0.08em;
    text-transform:uppercase; }}
</style>
<div id="captions" data-composition-id="captions" data-width="1080" data-height="1920">
  {chr(10).join('  ' + c for c in cap_html)}
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  {chr(10).join('  ' + j for j in cap_js)}
  window.__timelines["captions"] = tl;
</script>
</template>
"""
(out / "compositions" / "captions.html").write_text(captions)

# ---------------- location title with ink underline (local time 0 -> 6) ----------------
# The ink stroke is written by a pen nib travelling the path, then it stays as the underline.
INK_PATH = ("M 18 64 C 40 30, 74 26, 70 54 C 66 80, 30 78, 44 58 "
            "C 70 26, 220 70, 420 52 S 700 40, 820 50")
title = f"""<template>
<style>
  #title {{ position:absolute; inset:0; }}
  #title-scrim {{ position:absolute; left:0; right:0; top:820px; height:640px; opacity:0;
    background:linear-gradient(180deg, rgba(8,12,24,0) 0%, rgba(8,12,24,0.62) 38%, rgba(8,12,24,0.70) 100%); }}
  #title-block {{ position:absolute; left:64px; top:930px; width:860px; overflow:visible; }}
  #title-kicker {{ font-family:'Inter',sans-serif; font-weight:700; font-size:30px; letter-spacing:0.22em;
    text-transform:uppercase; color:{YELLOW}; margin-bottom:14px; opacity:0; }}
  #title-l1, #title-l2 {{ display:block; font-family:'Montserrat',sans-serif; font-weight:900; font-size:116px;
    line-height:0.98; letter-spacing:-0.025em; color:#fff; text-shadow:0 4px 18px rgba(0,0,0,0.45); white-space:nowrap; }}
  #title .tw {{ display:inline-block; opacity:0; }}
  #title-ink {{ position:absolute; left:-14px; top:226px; width:860px; height:110px; overflow:visible; }}
  #title-sub {{ margin-top:74px; font-family:'Inter',sans-serif; font-weight:700; font-size:44px; color:#fff;
    letter-spacing:0.005em; text-shadow:0 2px 10px rgba(0,0,0,0.5); white-space:nowrap; }}
  #title-sub .sw {{ display:inline-block; opacity:0; }}
  #title-sub .dot {{ color:{YELLOW}; }}
  #title-pen {{ position:absolute; left:0; top:0; width:120px; height:120px; opacity:0; overflow:visible; }}
</style>
<div id="title" data-composition-id="title" data-width="1080" data-height="1920">
  <div id="title-scrim" class="clip" data-start="0" data-duration="{TITLE[1]:.2f}"></div>
  <div id="title-block" class="clip" data-start="0" data-duration="{TITLE[1]:.2f}" data-layout-allow-overflow>
    <div id="title-kicker">Khamis, 29 Oktober</div>
    <span id="title-l1"><span class="tw" id="title-w0">Pesta</span> <span class="tw" id="title-w1">Buku</span></span>
    <span id="title-l2"><span class="tw" id="title-w2">Nogori</span> <span class="tw" id="title-w3">2026</span></span>
    <svg id="title-ink" viewBox="0 0 860 110" data-layout-allow-overflow>
      <defs>
        <filter id="title-rough" x="-5%" y="-40%" width="110%" height="180%">
          <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="2" seed="7" result="n"/>
          <feDisplacementMap in="SourceGraphic" in2="n" scale="5"/>
        </filter>
      </defs>
      <path id="title-bleed" d="{INK_PATH}" fill="none" stroke="{YELLOW}" stroke-opacity="0.28"
            stroke-width="22" stroke-linecap="round" stroke-linejoin="round" filter="url(#title-rough)"/>
      <path id="title-stroke" d="{INK_PATH}" fill="none" stroke="{YELLOW}" stroke-width="11"
            stroke-linecap="round" stroke-linejoin="round" filter="url(#title-rough)"/>
      <g id="title-pen">
        <!-- fountain-pen nib: tip at (0,0), body trailing up-right -->
        <path d="M0 0 L14 -30 L30 -22 Z" fill="{YELLOW}"/>
        <path d="M14 -30 L58 -112 L82 -100 L30 -22 Z" fill="#F4F1EA"/>
        <path d="M22 -27 L66 -106" stroke="{NAVY}" stroke-width="3"/>
        <circle cx="0" cy="0" r="5" fill="#fff"/>
      </g>
    </svg>
    <div id="title-sub"><span class="sw" id="title-s0">Meet</span> <span class="sw" id="title-s1">&amp;</span>
      <span class="sw" id="title-s2">Greet</span> <span class="sw" id="title-s3">Dr</span>
      <span class="sw" id="title-s4">Azren</span> <span class="sw dot" id="title-s5">•</span>
      <span class="sw" id="title-s6">USIM</span></div>
  </div>
</div>
<script>
  gsap.registerPlugin(MotionPathPlugin);
  const tl = gsap.timeline({{ paused: true }});
  const len = document.querySelector("#title-stroke").getTotalLength();
  tl.fromTo("#title-scrim", {{opacity:0}}, {{opacity:1, duration:0.4, ease:"power2.out"}}, 0.0);
  // title words blur in, a word every 70 ms, no slide
  ["#title-w0","#title-w1","#title-w2","#title-w3"].forEach((s, i) =>
    tl.fromTo(s, {{opacity:0, filter:"blur(10px)"}}, {{opacity:1, filter:"blur(0px)", duration:0.16, ease:"power3.out"}},
              0.12 + i * 0.07 + (i > 1 ? 0.12 : 0)));
  // the pen writes the ink line: stroke reveals behind the nib travelling the same path
  tl.fromTo(["#title-stroke","#title-bleed"], {{strokeDasharray:len, strokeDashoffset:len}},
            {{strokeDashoffset:0, duration:1.05, ease:"power2.inOut"}}, 0.62);
  tl.fromTo("#title-pen", {{opacity:0}}, {{opacity:1, duration:0.12}}, 0.56);
  tl.fromTo("#title-pen", {{motionPath:{{path:"#title-stroke", align:"#title-stroke", alignOrigin:[0,0], start:0, end:0}}}},
            {{motionPath:{{path:"#title-stroke", align:"#title-stroke", alignOrigin:[0,0], start:0, end:1}},
              duration:1.05, ease:"power2.inOut"}}, 0.62);
  tl.to("#title-pen", {{opacity:0, x:"+=40", y:"-=30", duration:0.25, ease:"power2.in"}}, 1.70);
  // kicker + subtitle land after the line is written
  tl.fromTo("#title-kicker", {{opacity:0, filter:"blur(6px)"}}, {{opacity:1, filter:"blur(0px)", duration:0.2, ease:"power3.out"}}, 0.02);
  ["#title-s0","#title-s1","#title-s2","#title-s3","#title-s4","#title-s5","#title-s6"].forEach((s, i) =>
    tl.fromTo(s, {{opacity:0, color:"#9aa3b5"}}, {{opacity:1, color:"#ffffff", duration:0.12, ease:"none"}}, 1.40 + i * 0.07));
  tl.set("#title-s5", {{color:"{YELLOW}"}}, 1.40 + 5 * 0.07 + 0.12);
  // exit: blur out word by word, scrim fades with it
  tl.to(["#title-kicker","#title-w0","#title-w1","#title-w2","#title-w3","#title-ink","#title-sub"],
        {{opacity:0, filter:"blur(8px)", duration:0.2, ease:"power2.in", stagger:0.03}}, {TITLE[1] - 0.48:.2f});
  tl.to("#title-scrim", {{opacity:0, duration:0.3, ease:"power2.in"}}, {TITLE[1] - 0.36:.2f});
  window.__timelines["title"] = tl;
</script>
</template>
"""
(out / "compositions" / "title.html").write_text(title)

# ---------------- closing thank-you (local 0 -> 5) ----------------
close_words = [("Terima", 0), ("kasih,", 0), ("warga", 1), ("Pesta", 1), ("Buku", 1), ("Nogori.", 1)]
spans = {0: [], 1: []}
for i, (w, ln) in enumerate(close_words):
    spans[ln].append(f'<span class="cw" id="close-w{i}">{html.escape(w)}</span>')
closing = f"""<template>
<style>
  #closing {{ position:absolute; inset:0; }}
  #close-scrim {{ position:absolute; left:0; right:0; top:900px; height:560px; opacity:0;
    background:linear-gradient(180deg, rgba(8,12,24,0) 0%, rgba(8,12,24,0.58) 45%, rgba(8,12,24,0.66) 100%); }}
  #close-block {{ position:absolute; left:64px; right:140px; top:1010px; }}
  #close-l1 {{ display:block; font-family:'Montserrat',sans-serif; font-weight:900; font-size:104px; line-height:1.0;
    letter-spacing:-0.02em; color:#fff; text-shadow:0 4px 18px rgba(0,0,0,0.45); white-space:nowrap; }}
  #close-l2 {{ display:block; margin-top:14px; font-family:'Montserrat',sans-serif; font-weight:800; font-size:58px;
    line-height:1.08; color:#fff; text-shadow:0 3px 12px rgba(0,0,0,0.5); white-space:nowrap; }}
  #closing .cw {{ display:inline-block; opacity:0; }}
  #close-w3, #close-w4, #close-w5 {{ color:{YELLOW}; }}
</style>
<div id="closing" data-composition-id="closing" data-width="1080" data-height="1920">
  <div id="close-scrim" class="clip" data-start="0" data-duration="{CLOSE[1]:.2f}"></div>
  <div id="close-block" class="clip" data-start="0" data-duration="{CLOSE[1]:.2f}" data-layout-allow-overflow>
    <span id="close-l1">{" ".join(spans[0])}</span>
    <span id="close-l2">{" ".join(spans[1])}</span>
  </div>
</div>
<script>
  const tl = gsap.timeline({{ paused: true }});
  tl.fromTo("#close-scrim", {{opacity:0}}, {{opacity:1, duration:0.6, ease:"power2.out"}}, 0.25);
  // slower, warmer entrance than the opening title: words drift in from light grey
  {chr(10).join(f'  tl.fromTo("#close-w{i}", {{opacity:0, filter:"blur(8px)", color:"#c9cfdb"}}, {{opacity:1, filter:"blur(0px)", color:"{YELLOW if i >= 3 else "#ffffff"}", duration:0.32, ease:"power2.out"}}, {0.55 + i * 0.14 + (0.25 if i >= 2 else 0):.2f});' for i in range(len(close_words)))}
  tl.to("#close-block", {{opacity:0, filter:"blur(8px)", duration:0.25, ease:"power2.in"}}, {CLOSE[1] - 0.3:.2f});
  tl.to("#close-scrim", {{opacity:0, duration:0.35, ease:"power2.in"}}, {CLOSE[1] - 0.4:.2f});
  window.__timelines["closing"] = tl;
</script>
</template>
"""
(out / "compositions" / "closing.html").write_text(closing)

# ---------------- root ----------------
index = f"""<!doctype html>
<html lang="ms">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=1080, height=1920" />
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/MotionPathPlugin.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html, body {{ width:1080px; height:1920px; overflow:hidden; background:transparent; }}
  #main {{ position:relative; width:1080px; height:1920px; }}
</style>
</head>
<body>
<div id="main" data-composition-id="main" data-start="0" data-duration="{TOTAL}" data-width="1080" data-height="1920">
  <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html"
       data-start="0" data-duration="{cap_end}" data-track-index="2" data-track-kind="captions"
       data-width="1080" data-height="1920"></div>
  <div id="title" data-composition-id="title" data-composition-src="compositions/title.html"
       data-start="{TITLE[0]}" data-duration="{TITLE[1]}" data-track-index="1" data-track-kind="graphics"
       data-width="1080" data-height="1920"></div>
  <div id="closing" data-composition-id="closing" data-composition-src="compositions/closing.html"
       data-start="{CLOSE[0]}" data-duration="{CLOSE[1]}" data-track-index="1" data-track-kind="graphics"
       data-width="1080" data-height="1920"></div>
</div>
<script>
  window.__timelines = window.__timelines || {{}};
  window.__timelines["main"] = gsap.timeline({{ paused: true }});
</script>
</body>
</html>
"""
(out / "index.html").write_text(index)
print("wrote overlay project to", out)
