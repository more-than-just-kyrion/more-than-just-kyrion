"""
build.py - regenerate everything from profile.toml

  assets/header.svg        animated ASCII header for the README
  README.md                the GitHub profile README
  docs/index.html          the GitHub Pages about page (+ docs/assets/*)

The header art is the exact character grid behind assets/avatar.png, pulled
from tools/ghost_avatar.py, re-drawn as live SVG text.

usage:  python tools/build.py
"""
import html
import math
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ghost_avatar as g  # noqa: E402  (builds the grid on import)

P = tomllib.loads((ROOT / "profile.toml").read_text(encoding="utf-8"))

# palette, shared with the avatar
C = {
    "bg": "#06070c", "panel": "#0a0d14", "line": "#1a1f2c",
    "amber": "#e1b469", "green": "#69cd8c", "cyan": "#69d7c8",
    "magenta": "#c85fa0", "violet": "#8a80b8", "text": "#b9b4d0", "dim": "#5d5a78",
}


def esc(s):
    return html.escape(str(s), quote=True)


def hexc(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def grade(rgb, x, y):
    """match the PNG's post-processing: vignette, soft knee, desaturate"""
    r = math.hypot(x, y)
    t = min(max((r - 0.75) / 0.5, 0), 1)
    vig = 0.35 + 0.65 * (1 - t * t * (3 - 2 * t))
    out = [c * vig for c in rgb]
    knee = 170.0
    out = [min(c, knee) + (255 - knee) * (1 - math.exp(-max(c - knee, 0) / (255 - knee))) for c in out]
    lum = 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]
    out = [lum + (c - lum) * 0.85 for c in out]
    return [max(0, min(255, round(c / 6) * 6)) for c in out]


# ---------------------------------------------------------------- header ---
def build_header():
    W, H = 1000, 440
    AX, AY, CW, CH = 12, 10, 5.0, 10.0          # art origin and cell size
    BOX = set("─│┌┐└┘")
    BLOCK = set("▀▄█▪")

    runs = {"plain": [], "glow": [], "glitch": []}
    rects = {"plain": [], "glow": []}
    paths = {}                                   # colour -> path data
    glitch_rows = set(getattr(g, "GLITCH", {}))

    for r in range(g.ROWS):
        cur = {"plain": None, "glow": None, "glitch": None}
        for c in range(g.COLS):
            ch = g.chars[r][c]
            x0, y0 = AX + c * CW, AY + r * CH
            if g.has_bg[r, c]:
                rects["plain"].append((x0, y0, CW + 0.05, CH + 0.05, hexc(g.cellbg[r, c])))
            if ch == " ":
                continue
            col = grade(g.color[r, c], g.X[r, c], g.Y[r, c])
            if max(col) < 14:
                continue
            hx = hexc(col)
            layer = "glow" if g.glow[r, c] >= 0.45 else ("glitch" if r in glitch_rows else "plain")

            if ch in BLOCK:
                h = {"▀": (0, CH / 2), "▄": (CH / 2, CH / 2), "█": (0, CH), "▪": (CH * .35, CH * .3)}[ch]
                w, dx = (CW, 0) if ch != "▪" else (CW * .5, CW * .25)
                rects["glow" if layer == "glow" else "plain"].append((x0 + dx, y0 + h[0], w + 0.05, h[1] + 0.05, hx))
                continue
            if ch in BOX:
                mx, my = x0 + CW / 2, y0 + CH / 2
                seg = {"─": f"M{x0:.1f} {my:.1f}h{CW}", "│": f"M{mx:.1f} {y0:.1f}v{CH}",
                       "┌": f"M{x0 + CW:.1f} {my:.1f}H{mx:.1f}V{y0 + CH:.1f}",
                       "┐": f"M{x0:.1f} {my:.1f}H{mx:.1f}V{y0 + CH:.1f}",
                       "└": f"M{x0 + CW:.1f} {my:.1f}H{mx:.1f}V{y0:.1f}",
                       "┘": f"M{x0:.1f} {my:.1f}H{mx:.1f}V{y0:.1f}"}[ch]
                paths.setdefault(hx, []).append(seg)
                continue

            run = cur[layer]
            if run and run["fill"] == hx:
                run["xs"].append(x0 + CW / 2)
                run["txt"] += ch
            else:
                run = {"y": y0 + CH * 0.8, "fill": hx, "xs": [x0 + CW / 2], "txt": ch}
                runs[layer].append(run)
                cur[layer] = run

    def text_block(rs):
        return "".join(
            f'<text y="{r["y"]:.1f}" fill="{r["fill"]}" x="{" ".join(f"{v:.1f}" for v in r["xs"])}">{esc(r["txt"])}</text>'
            for r in rs)

    def rect_block(rs):
        return "".join(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.2f}" height="{h:.2f}" fill="{f}"/>' for x, y, w, h, f in rs)

    box_paths = "".join(f'<path d="{"".join(d)}" stroke="{hx}"/>' for hx, d in paths.items())

    # terminal panel
    TX, TY, TW, TH = 468, 44, 506, 352
    handle = P["handle"]

    def clip(s, n=48):
        return s if len(s) <= n else s[: n - 1] + "…"

    lines = [
        [("$ ", C["amber"]), ("whoami", C["green"])],
        [(handle, C["cyan"])],
        [("$ ", C["amber"]), ("cat tagline", C["green"])],
        [(clip(P["tagline"]), C["text"])],
        [("$ ", C["amber"]), ("ls ~/interests", C["green"])],
        [(clip("  ".join(P["interests"])), C["violet"])],
        [("$ ", C["amber"]), ("cat status", C["green"])],
        [(clip(P["status"]), C["text"])],
        [("$ ", C["amber"])],
    ]
    term = []
    for i, segs in enumerate(lines):
        spans = "".join(f'<tspan fill="{col}">{esc(t)}</tspan>' for t, col in segs)
        y = TY + 72 + i * 30
        term.append(f'<text xml:space="preserve" class="ln" style="animation-delay:{0.25 + i * 0.22:.2f}s" x="{TX + 24}" y="{y}">{spans}</text>')
    cur_y = TY + 72 + (len(lines) - 1) * 30
    cursor = f'<rect class="cursor" x="{TX + 24 + 2 * 9.05:.1f}" y="{cur_y - 13}" width="9" height="16" fill="{C["green"]}"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="ASCII-art hooded figure with glowing eyes beside a terminal reading whoami: {esc(handle)}">
<style>
  .art {{ font: 700 8.6px ui-monospace, "Cascadia Mono", Consolas, Menlo, "DejaVu Sans Mono", monospace; text-anchor: middle; }}
  .term {{ font: 15px ui-monospace, "Cascadia Mono", Consolas, Menlo, "DejaVu Sans Mono", monospace; white-space: pre; }}
  .box path {{ fill: none; stroke-width: 1; }}
  .eyes {{ transform-box: fill-box; transform-origin: center; animation: blink 7s infinite; }}
  .glitch {{ animation: glitch 9s infinite; }}
  .ln {{ animation: type .01s both; }}
  .cursor {{ animation: cur 1.1s steps(1) infinite; }}
  @keyframes blink {{ 0%, 93%, 97%, 100% {{ transform: scaleY(1); }} 95% {{ transform: scaleY(.12); }} }}
  @keyframes glitch {{ 0%, 60%, 63%, 100% {{ transform: translateX(0); opacity: 1; }} 61% {{ transform: translateX(6px); opacity: .6; }} 62% {{ transform: translateX(-4px); }} }}
  @keyframes type {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes cur {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .eyes, .glitch, .ln, .cursor {{ animation: none; }} }}
</style>
<defs>
  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="2.4" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <radialGradient id="eyewash" cx="{AX + 0.5 * g.COLS * CW}" cy="{AY + (1 + g.EYES[0][1]) / 2 * g.ROWS * CH}" r="90" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="{C["cyan"]}" stop-opacity=".10"/><stop offset="1" stop-color="{C["cyan"]}" stop-opacity="0"/>
  </radialGradient>
</defs>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="14" fill="{C["bg"]}" stroke="{C["line"]}"/>
<rect x="{AX}" y="{AY}" width="{g.COLS * CW}" height="{g.ROWS * CH}" fill="url(#eyewash)"/>
<g class="art">
  <g>{rect_block(rects["plain"])}</g>
  <g class="box">{box_paths}</g>
  <g>{text_block(runs["plain"])}</g>
  <g class="glitch">{text_block(runs["glitch"])}</g>
  <g filter="url(#glow)">{text_block(runs["glow"])}<g class="eyes">{rect_block(rects["glow"])}</g></g>
</g>
<g class="term">
  <rect x="{TX}" y="{TY}" width="{TW}" height="{TH}" rx="10" fill="{C["panel"]}" stroke="{C["line"]}"/>
  <path d="M{TX} {TY + 34}h{TW}" stroke="{C["line"]}"/>
  <circle cx="{TX + 20}" cy="{TY + 17}" r="5" fill="{C["magenta"]}" opacity=".7"/>
  <circle cx="{TX + 38}" cy="{TY + 17}" r="5" fill="{C["amber"]}" opacity=".7"/>
  <circle cx="{TX + 56}" cy="{TY + 17}" r="5" fill="{C["green"]}" opacity=".7"/>
  <text x="{TX + TW / 2}" y="{TY + 22}" fill="{C["dim"]}" text-anchor="middle" style="font-size:12px">~/{esc(handle)}</text>
  {"".join(term)}
  {cursor}
</g>
</svg>
'''
    for dst in (ROOT / "assets" / "header.svg", ROOT / "docs" / "assets" / "header.svg"):
        dst.write_text(svg, encoding="utf-8")
    shutil.copy(ROOT / "assets" / "avatar.png", ROOT / "docs" / "assets" / "avatar.png")
    return len(svg)


# ---------------------------------------------------------------- README ---
def paragraphs(text):
    return [" ".join(p.split()) for p in text.strip().split("\n\n") if p.strip()]


def build_readme():
    h = P["handle"]
    site = f"https://{h}.github.io/{h}/"
    out = [
        '<p align="center">',
        f'  <img src="assets/header.svg" width="100%" alt="ASCII-art hooded figure with glowing eyes beside a terminal: whoami → {esc(h)}">',
        "</p>",
        "",
        f'<p align="center"><code>{esc(P["tagline"])}</code> &nbsp;·&nbsp; <a href="{site}">about page ↗</a></p>',
        "",
        "### `$ cat about.md`",
        "",
        *[p + "\n" for p in paragraphs(P["about"])],
        "### `$ tail now.log`",
        "",
        *[f"- {n}" for n in P["now"]],
        "",
        "### `$ ls ~/stack`",
        "",
        "```text",
        *[f"{k:<11}{'  '.join(v)}" for k, v in P["stack"].items()],
        "```",
        "",
        "### `$ ls ~/projects`",
        "",
        "| | |",
        "|---|---|",
        *[f"| [`{p['name']}`]({p['url']}) | {p['desc']} |" if p.get("url") else f"| `{p['name']}` | `{p['desc']}` |"
          for p in P["projects"]],
        "",
        "### `$ ./contact`",
        "",
        " · ".join(f"[{c['label']}]({c['url']})" for c in P["contact"]),
        "",
        "<sub>header &amp; avatar are generated from ASCII by <a href=\"tools/\"><code>tools/</code></a> — no pixels were drawn by hand.</sub>",
        "",
    ]
    (ROOT / "README.md").write_text("\n".join(out), encoding="utf-8")


# ------------------------------------------------------------- Pages site ---
def build_site():
    h = esc(P["handle"])

    def section(cmd, body):
        return f'<section><h2><span class="p">$</span> {cmd}</h2>{body}</section>'

    about = "".join(f"<p>{esc(p)}</p>" for p in paragraphs(P["about"]))
    now = "<ul>" + "".join(f"<li>{esc(n)}</li>" for n in P["now"]) + "</ul>"
    stack = "<dl>" + "".join(
        f"<dt>{esc(k)}</dt><dd>{'  '.join(esc(t) for t in v)}</dd>" for k, v in P["stack"].items()) + "</dl>"
    projects = "<ul class=\"proj\">" + "".join(
        (f'<li><a href="{esc(p["url"])}">{esc(p["name"])}</a><span>{esc(p["desc"])}</span></li>' if p.get("url")
         else f'<li class="x"><span class="n">{esc(p["name"])}</span><span>{esc(p["desc"])}</span></li>')
        for p in P["projects"]) + "</ul>"
    contact = '<p class="links">' + "".join(
        f'<a href="{esc(c["url"])}">{esc(c["label"])}</a>' for c in P["contact"]) + "</p>"

    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h} · whoami</title>
<meta name="description" content="{esc(P["tagline"])}">
<meta property="og:title" content="{h}">
<meta property="og:description" content="{esc(P["tagline"])}">
<meta property="og:image" content="assets/avatar.png">
<link rel="icon" href="assets/avatar.png">
<style>
  :root {{
    --bg: {C["bg"]}; --panel: {C["panel"]}; --line: {C["line"]};
    --text: {C["text"]}; --dim: {C["dim"]}; --amber: {C["amber"]};
    --green: {C["green"]}; --cyan: {C["cyan"]}; --magenta: {C["magenta"]}; --violet: {C["violet"]};
    --mono: ui-monospace, "Cascadia Code", "JetBrains Mono", Consolas, Menlo, "DejaVu Sans Mono", monospace;
  }}
  * {{ box-sizing: border-box; }}
  html {{ background: var(--bg); color-scheme: dark; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font: 15px/1.7 var(--mono); }}
  body::after {{ content: ""; position: fixed; inset: 0; pointer-events: none;
    background: repeating-linear-gradient(transparent 0 2px, rgba(0,0,0,.14) 2px 3px); }}
  main {{ max-width: 880px; margin: 0 auto; padding: 32px 16px 64px; }}
  header img {{ width: 100%; height: auto; display: block; }}
  .tag {{ text-align: center; color: var(--dim); margin: 14px auto 8px; max-width: none; }}
  .tag code {{ color: var(--violet); }}
  section {{ border-top: 1px solid var(--line); padding: 22px 0 6px; }}
  h2 {{ font-size: 15px; font-weight: 600; margin: 0 0 12px; color: var(--green); }}
  h2 .p {{ color: var(--amber); }}
  p {{ margin: 0 0 12px; max-width: 70ch; }}
  ul {{ margin: 0 0 12px; padding: 0; list-style: none; }}
  li {{ padding-left: 1.6em; position: relative; }}
  li::before {{ content: ">"; position: absolute; left: 0; color: var(--dim); }}
  dl {{ display: grid; grid-template-columns: 11ch 1fr; gap: 2px 12px; margin: 0 0 12px; }}
  dt {{ color: var(--dim); }}
  dd {{ margin: 0; white-space: pre-wrap; color: var(--violet); }}
  .proj li {{ display: flex; flex-wrap: wrap; gap: 0 14px; }}
  .proj span {{ color: var(--dim); }}
  .proj .x .n {{ color: var(--violet); }}
  a {{ color: var(--cyan); text-decoration: none; border-bottom: 1px dotted currentColor; }}
  a:hover, a:focus-visible {{ color: var(--bg); background: var(--cyan); outline: none; }}
  .links {{ display: flex; flex-wrap: wrap; gap: 8px 20px; }}
  footer {{ border-top: 1px solid var(--line); margin-top: 16px; padding-top: 18px; color: var(--dim); font-size: 13px; }}
  .cur {{ display: inline-block; width: .6em; height: 1.05em; vertical-align: text-bottom; background: var(--green);
    animation: cur 1.1s steps(1) infinite; }}
  @keyframes cur {{ 50% {{ opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .cur {{ animation: none; }} }}
  @media (max-width: 560px) {{ body {{ font-size: 14px; }} dl {{ grid-template-columns: 1fr; }} dd {{ margin-bottom: 8px; }} }}
</style>
</head>
<body>
<main>
  <header>
    <img src="assets/header.svg" width="1000" height="440" alt="ASCII-art hooded figure with glowing eyes beside a terminal: whoami → {h}">
    <p class="tag"><code>{esc(P["tagline"])}</code></p>
  </header>
  {section("cat about.md", about)}
  {section("tail now.log", now)}
  {section("ls ~/stack", stack)}
  {section("ls ~/projects", projects)}
  {section("./contact", contact)}
  <footer><span class="p" style="color:var(--amber)">$</span> <span class="cur" aria-hidden="true"></span>
    <p style="margin-top:10px">built from ASCII · <a href="https://github.com/{h}/{h}">source</a></p></footer>
</main>
</body>
</html>
'''
    (ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")


if __name__ == "__main__":
    n = build_header()
    build_readme()
    build_site()
    print(f"header.svg {n / 1024:.0f} KB · README.md · docs/index.html")
