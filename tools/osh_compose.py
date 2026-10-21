"""Generate the HyperFrames composition (reel/index.html) for the OSH Mega Day reel from its EDL.

Usage: python3 osh_compose.py EDL.json OUT_HTML

Media placement (plates, still, light leaks, freeze cut-out, soundtrack) is written as static
HTML so the HyperFrames compiler sees every clip; all motion (camera moves, whip pans, zoom
transitions, flashes, kinetic type, doodles, sticker freeze, Ken Burns, fade) is built in one
paused GSAP timeline from the same EDL data, so picture, type and sound share one beat grid.
"""
import json
import sys
from pathlib import Path

edl = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
W, H = edl["canvas"]["w"], edl["canvas"]["h"]
DUR = edl["duration"]
shots = edl["shots"]

# ---------------------------------------------------------------- static media
plates = []
for i, s in enumerate(shots):
    sid, t, d = s["id"], s["t"], s["dur"]
    if s.get("still"):
        media = (f'<img id="v-{sid}" class="clip plate" src="assets/plates/{sid}.jpg" alt="" '
                 f'data-start="{t}" data-duration="{d}" data-track-index="{1 + i % 2}" />')
    else:
        media = (f'<video id="v-{sid}" class="plate" src="assets/plates/{sid}.mp4" muted playsinline '
                 f'data-start="{t}" data-duration="{d}" data-media-start="0" '
                 f'data-track-index="{1 + i % 2}"></video>')
    extra = ""
    if s.get("freeze_at") is not None:
        ft = round(t + s["freeze_at"], 3)
        fd = round(d - s["freeze_at"], 3)
        extra = f"""
        <div id="fz-tint" class="clip fz-tint" data-start="{ft}" data-duration="{fd}" data-track-index="3"></div>
        <div id="fz-rays" class="clip fz-rays" data-start="{ft}" data-duration="{fd}" data-track-index="3">
          <svg viewBox="-540 -540 1080 1080" width="1600" height="1600"><g id="fz-rays-g">{''.join(
              f'<path d="M0 0 L{1100:.0f} {-70:.0f} L{1100:.0f} {70:.0f} Z" transform="rotate({k * 22.5})"/>' for k in range(16))}</g></svg>
        </div>
        <img id="fz-cut" class="clip fz-cut" src="assets/cut/{sid}_cut.png" alt="" data-start="{ft}" data-duration="{fd}" data-track-index="3" />"""
    plates.append(f"""
      <div class="cam" id="cam-{sid}"><div class="mv" id="mv-{sid}">
        {media}{extra}
      </div></div>""")

LEAKS = [  # id, file, start, dur, media_start
    ("lk-hook", "leak_warm", 0.0, 1.7, 1.0),
    ("lk-mont", "leak_warm", 16.8, 2.7, 0.0),
    ("lk-mid", "leak_blue", 20.8, 1.7, 2.0),
    ("lk-end", "leak_blue", 26.6, 3.4, 0.3),
]
leaks = "".join(
    f'\n      <div class="leak" id="{lid}"><video id="{lid}-v" src="assets/fx/{f}.mp4" muted playsinline '
    f'data-start="{st}" data-duration="{du}" data-media-start="{ms}" data-track-index="5"></video></div>'
    for lid, f, st, du, ms in LEAKS)

# ---------------------------------------------------------------- doodles (hand-drawn SVG)
SPARK = "M0,-38 C4,-8 8,-4 38,0 C8,4 4,8 0,38 C-4,8 -8,4 -38,0 C-8,-4 -4,-8 0,-38 Z"
HEART = ("M0,30 C-36,6 -58,-14 -48,-36 C-40,-54 -14,-56 0,-36 "
         "C14,-56 40,-54 48,-36 C58,-14 36,6 0,30 Z")


def spark(cls, x, y, s, color):
    return (f'<svg class="{cls} spark" style="left:{x}px;top:{y}px;width:{s}px;height:{s}px" '
            f'viewBox="-40 -40 80 80"><path d="{SPARK}" fill="{color}"/></svg>')


def heart(cls, x, y, s):
    return (f'<svg class="{cls} heart" style="left:{x}px;top:{y}px;width:{s}px;height:{s}px" '
            f'viewBox="-64 -64 128 128"><path d="{HEART}" fill="#2B6BFF" stroke="#fff" '
            f'stroke-width="9" stroke-linejoin="round"/></svg>')


def kinetic(tid, t, d, word, accent, doodle):
    chars = "".join(f'<span class="ch">{c}</span>' for c in word)
    return f"""
      <div id="t-{tid}" class="clip txt kin" data-start="{t}" data-duration="{d}" data-track-index="7">
        <div class="kin-wrap" id="{tid}-wrap">
          <div class="kin-word" id="{tid}-word" style="--acc:{accent}">{chars}</div>
          <div class="kin-strip" id="{tid}-strip" style="background:{accent}"><span>TOGETHER</span></div>
          {doodle}
        </div>
      </div>"""


ACC = {"yellow": "#FFD23F", "blue": "#2B6BFF", "orange": "#FF9F5A"}
laugh_doodle = ('<svg class="dd" id="laugh-dd" viewBox="0 0 1080 420" width="1080" height="420">'
                '<path class="draw" d="M150 70 L95 30 M140 130 L70 125 M160 185 L105 225" />'
                '<path class="draw" d="M930 70 L985 30 M940 130 L1010 125 M920 185 L975 225" /></svg>'
                + spark("laugh-sp", 820, 250, 70, "#FFD23F") + spark("laugh-sp", 190, 280, 48, "#fff"))
learn_doodle = ('<svg class="dd" id="learn-dd" viewBox="0 0 1080 700" width="1080" height="700">'
                '<path class="draw" d="M700 330 C790 340 840 380 850 470" />'
                '<path class="draw" d="M818 446 L851 482 L878 440" /></svg>'
                + spark("learn-sp", 160, 40, 56, "#FFD23F"))
grow_doodle = ('<svg class="dd" id="grow-dd" viewBox="0 0 1080 420" width="1080" height="420">'
               '<path class="draw" d="M905 300 C900 230 910 170 930 110" />'
               '<path class="draw" d="M898 140 L932 104 L960 146" />'
               '<path class="draw" d="M150 300 C140 250 150 200 175 160 M175 160 C200 175 210 200 200 225 M168 205 C145 195 130 205 128 225" /></svg>'
               + spark("grow-sp", 840, 20, 54, "#fff"))

texts = edl_texts = {x["id"]: x for x in edl["texts"]}
T = lambda k: (texts[k]["t"], texts[k]["dur"])

html_texts = f"""
      <div id="t-hook" class="clip txt" data-start="{T('hook')[0]}" data-duration="{T('hook')[1]}" data-track-index="7">
        <div class="hook" id="hook-wrap">
          <div class="paper-label" id="hook-label"><span>MENTAL HEALTH</span></div>
          <div class="hook-mid" id="hook-mid">{''.join(f'<span class="ch">{c if c != " " else "&nbsp;"}</span>' for c in "CAN BE")}</div>
          <div class="hook-fun-row"><div class="hook-fun" id="hook-fun">FUN!</div>{heart("hook-heart", 0, 0, 170).replace('style="left:0px;top:0px;', 'style="position:relative;')}</div>
          <svg class="dd" id="hook-sq" viewBox="0 0 1080 120" width="1080" height="120"><path class="draw" d="M250 60 C330 20 380 100 460 60 C540 20 590 100 670 60 C740 25 790 90 840 62" /></svg>
          {spark("hook-sp", 170, 140, 64, "#FFD23F")}{spark("hook-sp", 880, 330, 52, "#fff")}{spark("hook-sp", 120, 470, 40, "#fff")}
        </div>
      </div>
      {kinetic("laugh", *T("laugh"), "LAUGH", ACC["yellow"], laugh_doodle)}
      {kinetic("learn", *T("learn"), "LEARN", ACC["blue"], learn_doodle)}
      {kinetic("grow", *T("grow"), "GROW", ACC["orange"], grow_doodle)}
      <div id="t-fz" class="clip txt" data-start="16.45" data-duration="0.55" data-track-index="8">
        <div class="fz-tag" id="fz-tag"><span>OSH MEGA DAY 2026</span></div>
        {spark("fz-sp", 760, 470, 90, "#FFD23F")}{spark("fz-sp", 880, 640, 54, "#fff")}{spark("fz-sp", 200, 760, 60, "#FFD23F")}
      </div>
      <div id="t-scrim" class="clip scrim-low" data-start="{T('matters')[0] - 0.15}" data-duration="{T('matters')[1] + 0.15}" data-track-index="6"></div>
      <div id="t-matters" class="clip txt" data-start="{T('matters')[0]}" data-duration="{T('matters')[1]}" data-track-index="7">
        <div class="matters" id="matters-wrap">
          <div class="mt-line"><div class="mt-top" id="mt-top">EVERY CONVERSATION</div></div>
          <div class="mt-big" id="mt-big">{''.join(f'<span class="ch">{c}</span>' for c in "MATTERS.")}</div>
          <svg class="dd" id="mt-ul" viewBox="0 0 1080 60" width="1080" height="60"><path class="draw" d="M290 30 C450 12 640 46 800 24" /></svg>
        </div>
      </div>
      <div id="t-scrim-top" class="clip scrim-top" data-start="{T('spread')[0] - 0.3}" data-duration="{DUR - T('spread')[0] + 0.3}" data-track-index="6"></div>
      <div id="t-spread" class="clip txt" data-start="{T('spread')[0]}" data-duration="{T('spread')[1]}" data-track-index="7">
        <div class="spread" id="spread-wrap">
          <div class="spread-row"><div class="spread-txt" id="spread-txt">Spread Positivity</div>{heart("spread-heart", 0, 0, 130).replace('style="left:0px;top:0px;', 'style="position:relative;')}</div>
          <svg class="dd" id="spread-ul" viewBox="0 0 1080 60" width="1080" height="60"><path class="draw" d="M170 34 C400 14 700 50 930 22" /></svg>
          {heart("spread-h2", 120, -40, 70)}{heart("spread-h3", 905, 150, 56)}{spark("spread-sp", 860, -50, 60, "#FFD23F")}
        </div>
      </div>
      <div id="t-credit" class="clip txt" data-start="{T('credit')[0]}" data-duration="{T('credit')[1]}" data-track-index="8">
        <div class="credit" id="credit-pill">Dr Fakrul Azren&nbsp;&nbsp;|&nbsp;&nbsp;Mental Health Speaker</div>
      </div>"""

# ---------------------------------------------------------------- page
data = json.dumps({"shots": shots, "leaks": LEAKS, "duration": DUR, "texts": edl["texts"]})
page = f"""<!doctype html>
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>OSH Mega Day 2026 — highlight reel</title>
    <script src="assets/js/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "Poppins"; font-weight: 900; src: url("assets/fonts/Poppins-Black.ttf") format("truetype"); }}
      @font-face {{ font-family: "Poppins"; font-weight: 800; src: url("assets/fonts/Poppins-ExtraBold.ttf") format("truetype"); }}
      @font-face {{ font-family: "Poppins"; font-weight: 600; src: url("assets/fonts/Poppins-SemiBold.ttf") format("truetype"); }}
      @font-face {{ font-family: "Caveat"; font-weight: 400 700; src: url("assets/fonts/Caveat.ttf") format("truetype"); }}
      @font-face {{ font-family: "Playfair Display"; font-style: italic; font-weight: 400 900; src: url("assets/fonts/PlayfairDisplay-Italic.ttf") format("truetype"); }}
      :root {{ --blue: #2B6BFF; --navy: #0F2A6B; --deep: #1747C9; --yellow: #FFD23F; --orange: #FF9F5A; --paper: #FFFDF6; }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; background: #000; font-family: "Poppins", sans-serif; }}
      .cam, .mv, .leak, .fx-layer {{ position: absolute; inset: 0; }}
      .mv {{ transform-origin: 50% 50%; }}
      .plate {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      #mv-s24 {{ transform-origin: 46% 78%; }}
      .leak {{ mix-blend-mode: screen; opacity: 0; }}
      .leak video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      #flash {{ background: #fff; opacity: 0; }}
      #fade {{ background: #000; opacity: 0; }}
      #vignette {{ background: radial-gradient(ellipse 75% 60% at 50% 48%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.30) 100%); }}

      .fz-tint {{ background: var(--blue); mix-blend-mode: multiply; opacity: 0; }}
      .fz-rays {{ display: flex; align-items: center; justify-content: center; opacity: 0; }}
      .fz-rays svg {{ position: absolute; left: -10px; top: 120px; }}
      .fz-rays path {{ fill: var(--yellow); opacity: 0.35; }}
      .fz-cut {{ position: absolute; inset: 0; width: 100%; height: 100%; transform-origin: 55% 60%;
        filter: drop-shadow(7px 0 0 #fff) drop-shadow(-7px 0 0 #fff) drop-shadow(0 7px 0 #fff) drop-shadow(0 -7px 0 #fff) drop-shadow(0 18px 18px rgba(10,20,60,0.45)); }}

      .txt {{ pointer-events: none; }}
      .ch {{ display: inline-block; }}
      .dd {{ position: absolute; left: 0; overflow: visible; }}
      .dd path.draw {{ fill: none; stroke: var(--paper); stroke-width: 12; stroke-linecap: round; stroke-linejoin: round; }}
      .spark, .heart {{ position: absolute; overflow: visible; }}
      .outline {{ text-shadow: 0 0 0 transparent; }}

      .hook {{ position: absolute; left: 0; top: 270px; width: 100%; height: 640px; display: flex; flex-direction: column; align-items: center; }}
      .paper-label {{ background: var(--paper); padding: 14px 40px 6px; transform-origin: 0% 50%;
        clip-path: polygon(0 6%, 4% 0, 12% 5%, 22% 1%, 33% 6%, 45% 0, 57% 5%, 70% 1%, 82% 6%, 93% 0, 100% 5%, 99% 52%, 100% 96%, 90% 100%, 78% 95%, 66% 100%, 54% 95%, 41% 100%, 29% 95%, 17% 100%, 6% 95%, 0 100%, 1% 50%);
        box-shadow: 0 12px 0 rgba(15,42,107,0.35); }}
      .paper-label span {{ display: block; font-weight: 900; font-size: 92px; line-height: 1.1; letter-spacing: 0.01em; color: var(--deep); }}
      .hook-mid {{ margin-top: 18px; font-weight: 900; font-size: 128px; line-height: 1; color: #fff;
        text-shadow: 5px 5px 0 var(--navy), -5px 5px 0 var(--navy), 5px -5px 0 var(--navy), -5px -5px 0 var(--navy), 0 6px 0 var(--navy), 6px 0 0 var(--navy), -6px 0 0 var(--navy), 0 -6px 0 var(--navy), 0 16px 0 var(--deep); }}
      .hook-fun-row {{ display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: 4px; }}
      .hook-fun {{ font-weight: 900; font-size: 236px; line-height: 1.02; color: var(--yellow);
        text-shadow: 7px 7px 0 var(--navy), -7px 7px 0 var(--navy), 7px -7px 0 var(--navy), -7px -7px 0 var(--navy), 0 8px 0 var(--navy), 8px 0 0 var(--navy), -8px 0 0 var(--navy), 0 -8px 0 var(--navy), 0 22px 0 var(--deep); }}
      #hook-sq {{ top: 520px; }}
      #hook-sq path.draw {{ stroke: var(--orange); stroke-width: 16; }}

      .kin-wrap {{ position: absolute; left: 0; top: 300px; width: 100%; height: 420px; display: flex; flex-direction: column; align-items: center; }}
      .kin-word {{ font-weight: 900; font-size: 196px; line-height: 1.05; color: #fff; letter-spacing: 0.01em;
        text-shadow: 6px 6px 0 var(--navy), -6px 6px 0 var(--navy), 6px -6px 0 var(--navy), -6px -6px 0 var(--navy), 0 7px 0 var(--navy), 7px 0 0 var(--navy), -7px 0 0 var(--navy), 0 -7px 0 var(--navy), 0 20px 0 var(--acc); }}
      .kin-strip {{ margin-top: 10px; padding: 10px 46px 4px; transform: rotate(-2deg); box-shadow: 0 10px 0 rgba(15,42,107,0.35);
        clip-path: polygon(0 8%, 6% 0, 20% 6%, 36% 0, 52% 7%, 68% 0, 84% 6%, 100% 0, 99% 50%, 100% 100%, 84% 94%, 68% 100%, 52% 93%, 36% 100%, 20% 94%, 6% 100%, 0 92%, 1% 50%); }}
      .kin-strip span {{ display: block; font-weight: 800; font-size: 74px; line-height: 1.1; letter-spacing: 0.18em; color: var(--navy); }}
      #learn-strip span {{ color: #fff; }}
      #laugh-dd {{ top: -10px; }} #learn-dd {{ top: 0; }} #grow-dd {{ top: 0; }}
      #laugh-dd path.draw {{ stroke: var(--yellow); }}
      #learn-dd path.draw {{ stroke: var(--yellow); stroke-width: 13; }}
      #grow-dd path.draw {{ stroke: #9BE15D; stroke-width: 12; }}

      .fz-tag {{ position: absolute; left: 70px; top: 300px; background: var(--yellow); padding: 14px 30px 8px; transform-origin: 0 50%;
        box-shadow: 0 10px 0 rgba(15,42,107,0.4); clip-path: polygon(0 8%, 10% 0, 30% 6%, 50% 0, 70% 6%, 90% 0, 100% 8%, 99% 50%, 100% 92%, 90% 100%, 70% 94%, 50% 100%, 30% 94%, 10% 100%, 0 92%, 1% 50%); }}
      .fz-tag span {{ display: block; font-weight: 900; font-size: 58px; letter-spacing: 0.04em; color: var(--navy); }}

      .scrim-low {{ background: linear-gradient(to bottom, rgba(10,22,60,0) 48%, rgba(10,22,60,0.62) 72%, rgba(10,22,60,0.35) 100%); opacity: 0; }}
      .scrim-top {{ background: linear-gradient(to bottom, rgba(10,22,60,0.0) 8%, rgba(10,22,60,0.45) 24%, rgba(10,22,60,0.35) 40%, rgba(10,22,60,0) 52%); opacity: 0; }}
      .matters {{ position: absolute; left: 0; top: 1130px; width: 100%; display: flex; flex-direction: column; align-items: center; }}
      .mt-line {{ overflow: hidden; padding: 4px 0; }}
      .mt-top {{ font-weight: 600; font-size: 52px; letter-spacing: 0.16em; color: #fff; text-shadow: 0 3px 14px rgba(0,0,0,0.45); }}
      .mt-big {{ font-family: "Playfair Display", serif; font-style: italic; font-weight: 900; font-size: 176px; line-height: 1.05; color: #fff;
        text-shadow: 0 4px 24px rgba(10,22,60,0.55), 0 0 60px rgba(255,210,63,0.25); }}
      #mt-ul {{ top: 300px; }}
      #mt-ul path.draw {{ stroke: var(--yellow); stroke-width: 10; }}

      .spread {{ position: absolute; left: 0; top: 330px; width: 100%; height: 300px; display: flex; flex-direction: column; align-items: center; }}
      .spread-row {{ display: flex; align-items: center; gap: 8px; }}
      .spread-txt {{ font-family: "Caveat", cursive; font-weight: 700; font-size: 158px; line-height: 1.1; color: #fff;
        text-shadow: 4px 4px 0 var(--navy), -4px 4px 0 var(--navy), 4px -4px 0 var(--navy), -4px -4px 0 var(--navy), 0 5px 0 var(--navy), 5px 0 0 var(--navy), -5px 0 0 var(--navy), 0 -5px 0 var(--navy), 0 14px 0 var(--blue); }}
      #spread-ul {{ top: 190px; }}
      #spread-ul path.draw {{ stroke: var(--yellow); stroke-width: 11; }}
      .credit {{ position: absolute; left: 50%; top: 640px; transform: translateX(-50%); white-space: nowrap; background: rgba(15,42,107,0.88);
        border: 3px solid rgba(255,255,255,0.9); border-radius: 60px; padding: 14px 34px 10px; font-weight: 600; font-size: 34px; color: #fff; letter-spacing: 0.02em; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{DUR}" data-width="{W}" data-height="{H}" data-fps="30">
      {''.join(plates)}
      {leaks}
      <div class="fx-layer" id="vignette"></div>
      <div class="fx-layer" id="flash"></div>
      {html_texts}
      <div class="fx-layer" id="fade"></div>
      <audio id="soundtrack" src="assets/audio/mix.wav" data-start="0" data-duration="{DUR}" data-track-index="11" data-volume="1"></audio>
    </div>
    <script>
      const EDL = {data};
      const tl = gsap.timeline({{ paused: true }});
      // every tween is a lazy fromTo; the earliest "from" of each element/property is also pinned
      // at t=0 (see the end of the script) so any frame before a tween starts shows its start pose
      const firstFrom = new Map();
      const F = (sel, from, to, at) => {{
        const els = typeof sel === "string" ? document.querySelectorAll(sel) : [sel];
        els.forEach(el => {{
          const m = firstFrom.get(el) || {{}};
          firstFrom.set(el, m);
          for (const [k, v] of Object.entries(from)) if (!m[k] || at < m[k][0]) m[k] = [at, v];
        }});
        return tl.fromTo(sel, from, Object.assign({{ immediateRender: false }}, to), at);
      }};
      let seed = 7;
      const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

      // ---------------- camera: per-shot moves, whip pans, zoom-through, flashes
      gsap.set(".cam", {{ x: 0, scale: 1, filter: "blur(0px)" }});
      gsap.set(".mv", {{ scale: 1, x: 0, y: 0, rotation: 0 }});
      gsap.set("#flash, #fade", {{ opacity: 0 }});
      const shots = EDL.shots;
      shots.forEach((s, i) => {{
        const mv = "#mv-" + s.id, cam = "#cam-" + s.id;
        const t0 = s.t, t1 = s.t + s.dur, moveEnd = s.freeze_at != null ? t0 + s.freeze_at : t1;
        const md = moveEnd - t0;
        switch (s.move) {{
          case "crash_in":
            F(mv, {{ scale: 1.42, rotation: 3 }}, {{ scale: 1.0, rotation: 0, duration: 0.5, ease: "expo.out" }}, t0);
            F(mv, {{ scale: 1.0 }}, {{ scale: 1.05, duration: md - 0.72, ease: "none" }}, t0 + 0.5);
            break;
          case "settle":
            F(mv, {{ scale: 1.32 }}, {{ scale: 1.06, duration: 0.42, ease: "expo.out" }}, t0);
            F(mv, {{ scale: 1.06 }}, {{ scale: 1.1, duration: md - 0.42, ease: "none" }}, t0 + 0.42);
            break;
          case "drift_l": F(mv, {{ scale: 1.1, x: 45 }}, {{ x: -45, duration: md, ease: "none" }}, t0); break;
          case "drift_r": F(mv, {{ scale: 1.1, x: -45 }}, {{ x: 45, duration: md, ease: "none" }}, t0); break;
          case "push": F(mv, {{ scale: 1.03 }}, {{ scale: 1.12, duration: md, ease: "none" }}, t0); break;
          case "push_slow": F(mv, {{ scale: 1.02 }}, {{ scale: 1.09, duration: md, ease: "sine.inOut" }}, t0); break;
          case "punch":
            F(mv, {{ scale: 1.24 }}, {{ scale: 1.08, duration: 0.2, ease: "power3.out" }}, t0);
            F(mv, {{ scale: 1.08 }}, {{ scale: 1.12, duration: md - 0.2, ease: "none" }}, t0 + 0.2);
            break;
          case "shake": {{
            tl.set(mv, {{ scale: 1.12, x: 0, y: 0 }}, t0);
            for (let b = t0; b < moveEnd - 0.05; b += 0.25) {{
              const ax = (rnd() - 0.5) * 30, ay = (rnd() - 0.5) * 22;
              F(mv, {{ x: ax, y: ay }}, {{ x: 0, y: 0, duration: 0.2, ease: "power2.out" }}, b);
            }}
            break;
          }}
          case "kenburns": F(mv, {{ scale: 1.3 }}, {{ scale: 1.43, duration: md, ease: "sine.out" }}, t0); break;
        }}
        // transition in
        if (s.in === "whip_l" || s.in === "whip_r") {{
          const dir = s.in === "whip_l" ? 1 : -1;
          F(cam, {{ x: dir * 220, scale: 1.45, filter: "blur(26px)" }}, {{ x: 0, scale: 1, filter: "blur(0px)", duration: 0.16, ease: "power3.out" }}, t0);
        }} else if (s.in === "zoom") {{
          F(cam, {{ filter: "blur(14px)" }}, {{ filter: "blur(0px)", duration: 0.3, ease: "power2.out" }}, t0);
        }} else if (s.in === "flash") {{
          F("#flash", {{ opacity: t0 === 0 ? 1 : 0.8 }}, {{ opacity: 0, duration: t0 === 0 ? 0.35 : 0.2, ease: "power2.out" }}, t0);
        }}
        // transition out, driven by the next shot's entry
        const nx = shots[i + 1];
        if (nx && (nx.in === "whip_l" || nx.in === "whip_r")) {{
          const dir = nx.in === "whip_l" ? 1 : -1;
          F(cam, {{ x: 0, scale: 1, filter: "blur(0px)" }}, {{ x: -dir * 220, scale: 1.45, filter: "blur(26px)", duration: 0.12, ease: "power3.in" }}, t1 - 0.12);
        }} else if (nx && nx.in === "zoom") {{
          F(mv, {{ scale: 1.05 }}, {{ scale: 1.34, duration: 0.22, ease: "power2.in" }}, t1 - 0.22);
          F(cam, {{ filter: "blur(0px)" }}, {{ filter: "blur(14px)", duration: 0.22, ease: "power2.in" }}, t1 - 0.22);
        }}
      }});

      // ---------------- sticker freeze (s15): flash + shutter, blue tint, rays, cut-out pops out
      const fz = shots.find(s => s.freeze_at != null);
      if (fz) {{
        const ft = fz.t + fz.freeze_at;
        F("#flash", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.18, ease: "power2.out" }}, ft);
        F("#fz-tint", {{ opacity: 0 }}, {{ opacity: 0.78, duration: 0.1 }}, ft);
        F("#fz-rays", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.12 }}, ft);
        F("#fz-rays-g", {{ rotation: 0, svgOrigin: "0 0" }}, {{ rotation: 18, svgOrigin: "0 0", duration: 0.6, ease: "none" }}, ft);
        F("#fz-cut", {{ scale: 1, rotation: 0, y: 0 }}, {{ scale: 1.07, rotation: -2.5, y: -14, duration: 0.28, ease: "back.out(2.2)" }}, ft + 0.02);
      }}
      F("#fz-tag", {{ scaleX: 0, rotation: -14 }}, {{ scaleX: 1, rotation: -6, duration: 0.22, ease: "back.out(1.8)" }}, 16.47);
      document.querySelectorAll("#t-fz .spark").forEach((el, k) =>
        F(el, {{ scale: 0, rotation: -40 }}, {{ scale: 1, rotation: 0, duration: 0.25, ease: "back.out(3)" }}, 16.5 + k * 0.06));

      // ---------------- light leaks (Higgsfield plates, screen-blended)
      const leakKeys = {{
        "lk-hook": [[0.0, 0.0], [0.12, 0.55], [1.1, 0.25], [1.65, 0.0]],
        "lk-mont": [[16.8, 0.0], [17.05, 0.85], [17.8, 0.4], [18.8, 0.18], [19.45, 0.0]],
        "lk-mid":  [[20.8, 0.0], [21.1, 0.4], [22.4, 0.0]],
        "lk-end":  [[26.6, 0.0], [27.02, 0.9], [27.7, 0.35], [29.2, 0.3], [29.95, 0.0]],
      }};
      Object.entries(leakKeys).forEach(([id, keys]) => {{
        tl.set("#" + id, {{ opacity: 0 }}, 0);
        for (let k = 1; k < keys.length; k++)
          F("#" + id, {{ opacity: keys[k - 1][1] }}, {{ opacity: keys[k][1], duration: keys[k][0] - keys[k - 1][0], ease: "sine.inOut" }}, keys[k - 1][0]);
      }});

      // ---------------- doodle stroke drawing
      const draw = (sel, at, dur) => document.querySelectorAll(sel).forEach((p, k) => {{
        const L = Math.ceil(p.getTotalLength()) + 2;
        p.style.strokeDasharray = L + " " + L;
        F(p, {{ strokeDashoffset: L }}, {{ strokeDashoffset: 0, duration: dur, ease: "power2.out" }}, at + k * 0.08);
      }});
      const pop = (sel, at, stagger = 0.07) => document.querySelectorAll(sel).forEach((el, k) =>
        F(el, {{ scale: 0, rotation: -30 }}, {{ scale: 1, rotation: 0, duration: 0.3, ease: "back.out(3)" }}, at + k * stagger));
      const twinkle = (sel, from, to) => document.querySelectorAll(sel).forEach((el, k) => {{
        for (let b = from + 0.25 + k * 0.12; b < to - 0.3; b += 0.5)
          F(el, {{ scale: 1.25 }}, {{ scale: 1, duration: 0.3, ease: "power2.out" }}, b);
      }});

      // ---------------- HOOK: MENTAL HEALTH CAN BE FUN!
      const hk = EDL.texts.find(t => t.id === "hook");
      F("#hook-label", {{ scaleX: 0, rotation: -8, y: -30 }}, {{ scaleX: 1, rotation: -3, y: 0, duration: 0.26, ease: "back.out(1.6)" }}, 0.15);
      document.querySelectorAll("#hook-mid .ch").forEach((c, k) =>
        F(c, {{ y: 60, scale: 0, opacity: 0 }}, {{ y: 0, scale: 1, opacity: 1, duration: 0.24, ease: "back.out(2.4)" }}, 0.45 + k * 0.03));
      F("#hook-fun", {{ scale: 2.4, rotation: -12, opacity: 0 }}, {{ scale: 1, rotation: 4, opacity: 1, duration: 0.36, ease: "back.out(2)" }}, 0.75);
      F(".hook-heart", {{ scale: 0, rotation: -25 }}, {{ scale: 1, rotation: 8, duration: 0.32, ease: "back.out(3)" }}, 1.02);
      [1.5, 2.0, 2.5].forEach(b => F(".hook-heart", {{ scale: 1.18 }}, {{ scale: 1, duration: 0.35, ease: "power2.out" }}, b));
      draw("#hook-sq path", 1.05, 0.38);
      pop(".hook-sp", 1.1, 0.1);
      twinkle(".hook-sp", 1.4, 2.7);
      F("#hook-wrap", {{ y: 0 }}, {{ y: 26, duration: 2.5, ease: "none" }}, 0.15);
      F("#hook-wrap", {{ scale: 1, opacity: 1, filter: "blur(0px)" }}, {{ scale: 1.35, opacity: 0, filter: "blur(10px)", duration: 0.2, ease: "power2.in" }}, hk.t + hk.dur - 0.22);

      // ---------------- LAUGH / LEARN / GROW TOGETHER
      ["laugh", "learn", "grow"].forEach(id => {{
        const tx = EDL.texts.find(t => t.id === id), t0 = tx.t, t1 = tx.t + tx.dur;
        document.querySelectorAll("#" + id + "-word .ch").forEach((c, k) => {{
          const r = (rnd() - 0.5) * 30;
          F(c, {{ y: -140, rotation: r, opacity: 0 }}, {{ y: 0, rotation: 0, opacity: 1, duration: 0.3, ease: "back.out(1.9)" }}, t0 + k * 0.035);
        }});
        F("#" + id + "-strip", {{ clipPath: "inset(0% 100% 0% 0%)", scale: 1.1 }}, {{ clipPath: "inset(0% 0% 0% 0%)", scale: 1, duration: 0.26, ease: "power3.out" }}, t0 + 0.27);
        draw("#" + id + "-dd path", t0 + 0.35, 0.3);
        pop("." + id + "-sp", t0 + 0.4);
        F("#" + id + "-wrap", {{ y: -12, scale: 1 }}, {{ y: 18, scale: 1.04, duration: tx.dur, ease: "none" }}, t0);
        F("#" + id + "-wrap", {{ opacity: 1, filter: "blur(0px)" }}, {{ opacity: 0, filter: "blur(12px)", duration: 0.2, ease: "power2.in" }}, t1 - 0.22);
      }});

      // ---------------- EVERY CONVERSATION MATTERS.
      const mt = EDL.texts.find(t => t.id === "matters");
      F("#t-scrim", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.4 }}, mt.t - 0.15);
      F("#mt-top", {{ yPercent: 110 }}, {{ yPercent: 0, duration: 0.5, ease: "expo.out" }}, mt.t + 0.05);
      document.querySelectorAll("#mt-big .ch").forEach((c, k) =>
        F(c, {{ y: 40, opacity: 0, filter: "blur(10px)" }}, {{ y: 0, opacity: 1, filter: "blur(0px)", duration: 0.45, ease: "power3.out" }}, mt.t + 0.35 + k * 0.045));
      draw("#mt-ul path", mt.t + 0.85, 0.5);
      F("#matters-wrap", {{ scale: 1 }}, {{ scale: 1.04, duration: mt.dur, ease: "none" }}, mt.t);
      F("#matters-wrap", {{ opacity: 1, y: 0 }}, {{ opacity: 0, y: -30, duration: 0.25, ease: "power2.in" }}, mt.t + mt.dur - 0.28);
      F("#t-scrim", {{ opacity: 1 }}, {{ opacity: 0, duration: 0.3 }}, mt.t + mt.dur - 0.3);

      // ---------------- Spread Positivity + credit
      const sp = EDL.texts.find(t => t.id === "spread"), cr = EDL.texts.find(t => t.id === "credit");
      F("#t-scrim-top", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5 }}, sp.t - 0.3);
      F("#spread-txt", {{ clipPath: "inset(0% 100% 0% 0%)", y: 10 }}, {{ clipPath: "inset(0% 0% 0% 0%)", y: 0, duration: 0.7, ease: "power2.inOut" }}, sp.t);
      F(".spread-heart", {{ scale: 0, rotation: -25 }}, {{ scale: 1, rotation: 6, duration: 0.34, ease: "back.out(3)" }}, sp.t + 0.6);
      [28.5, 29.0].forEach(b => F(".spread-heart", {{ scale: 1.16 }}, {{ scale: 1, duration: 0.35, ease: "power2.out" }}, b));
      draw("#spread-ul path", sp.t + 0.65, 0.45);
      pop(".spread-h2, .spread-h3, .spread-sp", sp.t + 0.8, 0.12);
      F("#credit-pill", {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.45, ease: "power3.out" }}, cr.t);
      F("#spread-wrap", {{ y: 0 }}, {{ y: 14, duration: sp.dur, ease: "none" }}, sp.t);

      // ---------------- clean cinematic fade-out
      F("#fade", {{ opacity: 0 }}, {{ opacity: 1, duration: 0.72, ease: "power1.in" }}, EDL.duration - 0.75);

      firstFrom.forEach((m, el) => {{
        const o = {{}};
        for (const k in m) o[k] = m[k][1];
        tl.set(el, o, 0);
      }});

      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""
out.write_text(page)
print(f"wrote {out} ({len(shots)} shots, {DUR}s)")
