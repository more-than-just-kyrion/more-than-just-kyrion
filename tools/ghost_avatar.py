"""
ghost_avatar.py - colored ASCII-art profile image generator.

A hooded figure whose face is a void of binary, with happy-arc eyes and a
blinking cursor for a mouth:  ^_^  -- an emoticon, or a terminal prompt?

Outputs:
  ghost_avatar.png   500x500 GitHub avatar (circle-crop safe)
  ghost_avatar.ans   24-bit ANSI version, view with:  cat ghost_avatar.ans
"""
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SEED = 1337
random.seed(SEED)
rng = np.random.default_rng(SEED)

# ---------------------------------------------------------------- canvas ---
OUT = 500                       # GitHub's recommended avatar size
SIZE = OUT * 2                  # render at 2x, downsample for clean edges
COLS, ROWS = 84, 42             # coarse enough to stay crisp at 460px
CW, CH = SIZE / COLS, SIZE / ROWS
FONT = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 20)

BG = np.array([6, 7, 12], float)

# palette
CYAN = np.array([105, 215, 200], float)
MAGENTA = np.array([200, 95, 160], float)
GREEN = np.array([105, 205, 140], float)
AMBER = np.array([225, 180, 105], float)
EYE = np.array([195, 238, 228], float)
HOOD_DARK = np.array([20, 18, 38], float)
HOOD_LITE = np.array([112, 98, 178], float)

chars = [[" "] * COLS for _ in range(ROWS)]
color = np.zeros((ROWS, COLS, 3))
glow = np.zeros((ROWS, COLS))              # 0..1, how much a cell blooms
cellbg = np.zeros((ROWS, COLS, 3))
has_bg = np.zeros((ROWS, COLS), bool)

# cell-centre coordinates in [-1, 1], y pointing down
xs = (np.arange(COLS) + 0.5) / COLS * 2 - 1
ys = (np.arange(ROWS) + 0.5) / ROWS * 2 - 1
X, Y = np.meshgrid(xs, ys)


def put(r, c, ch, col, g=0.0):
    if 0 <= r < ROWS and 0 <= c < COLS:
        chars[r][c] = ch
        color[r, c] = np.clip(col, 0, 255)
        glow[r, c] = g


def cell_of(x, y):
    return int((y + 1) / 2 * ROWS), int((x + 1) / 2 * COLS)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def sd_ellipse(x, y, cx, cy, rx, ry_top, ry_bot=None):
    ry = ry_top if ry_bot is None else np.where(y < cy, ry_top, ry_bot)
    q = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return (q - 1) * np.minimum(rx, ry)


def value_noise(x, y, scale, seed):
    """cheap smooth 2D noise"""
    g = np.random.default_rng(seed).random((64, 64))
    fx, fy = x * scale + 32, y * scale + 32
    ix, iy = np.floor(fx).astype(int) % 63, np.floor(fy).astype(int) % 63
    tx, ty = fx - np.floor(fx), fy - np.floor(fy)
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a, b = g[iy, ix], g[iy, ix + 1]
    c, d = g[iy + 1, ix], g[iy + 1, ix + 1]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


# ---------------------------------------------------------------- shapes ---
head = sd_ellipse(X, Y, 0.0, -0.20, 0.47, 0.64, 0.50)       # egg-ish hood peak
shoulders = sd_ellipse(X, Y, 0.0, 1.08, 1.05, 0.76)
hood = smin(head, shoulders, 0.36)
face = sd_ellipse(X, Y, 0.0, -0.08, 0.27, 0.35, 0.38)

# pseudo-3D: a puffy height field over the hood (with the face carved out)
solid = np.maximum(hood, -face)
height = np.sqrt(np.clip(-solid / 0.30, 0, 1))
hy, hx = np.gradient(height, ys, xs)
nz = 1 / np.sqrt(hx ** 2 + hy ** 2 + 1)
NX, NY = -hx * nz, -hy * nz
L = np.array([-0.55, -0.55, 0.63]); L /= np.linalg.norm(L)
diffuse = np.clip(NX * L[0] + NY * L[1] + nz * L[2], 0, 1)
fresnel = 1 - nz

gy, gx = np.gradient(hood)
gl = np.hypot(gx, gy) + 1e-9
nx, ny = gx / gl, gy / gl                                   # outward normal

vignette = 1 - smoothstep(0.55, 1.05, np.hypot(X, Y))        # circle-crop safe
noise = value_noise(X, Y, 6, 7)

# ------------------------------------------------------- background rain ---
RAIN = "0123456789abcdef{}[]<>/\\|;:$#%&*+=~"
for c in range(COLS):
    for _ in range(random.choice([1, 1, 2])):
        head_r = random.randint(-10, ROWS + 10)
        length = random.randint(6, 22)
        for k in range(length):
            r = head_r - k
            if not (0 <= r < ROWS) or hood[r, c] < 0.012:
                continue
            fade = (1 - k / length) ** 1.6
            v = vignette[r, c]
            if k == 0:
                col = np.array([190, 255, 210]) * v
                g = 0.55 * v
            else:
                col = GREEN * (0.10 + 0.55 * fade) * v
                g = 0.0
            put(r, c, random.choice(RAIN), col, g)

# faint static in the empty gaps
for r in range(ROWS):
    for c in range(COLS):
        if chars[r][c] == " " and hood[r, c] > 0.012 and random.random() < 0.05:
            put(r, c, random.choice(".'`"), GREEN * 0.12 * vignette[r, c])

# ------------------------------------------------------------------ hood ---
RAMP = " .:-=+*#%@"
for r in range(ROWS):
    for c in range(COLS):
        d = hood[r, c]
        if d >= 0.012 or face[r, c] < 0:
            continue
        depth = -d
        x, y = X[r, c], Y[r, c]
        body = 0.06 + 0.52 * diffuse[r, c] ** 1.6
        # fabric folds draping down from the hood
        folds = 0.5 + 0.5 * np.sin(x * 11 + np.sin(y * 3) * 1.5 + y * 2.5)
        body += 0.18 * (folds - 0.5) * smoothstep(0.0, 0.6, y)
        # rim lights, strongest where the surface turns away from us
        rim = fresnel[r, c] ** 2.6
        rim_l = rim * max(0, -NX[r, c] / (1 - nz[r, c] + 1e-6)) * 1.1
        rim_r = rim * max(0, NX[r, c] / (1 - nz[r, c] + 1e-6)) * 1.0
        # the face-side rim is shadowed -- we only light the outer silhouette
        outer = smoothstep(0.02, 0.10, face[r, c])
        rim_l *= outer; rim_r *= outer
        body = float(np.clip(body * (0.9 + 0.2 * noise[r, c]), 0, 1))

        col = HOOD_DARK + (HOOD_LITE - HOOD_DARK) * body
        col = col + CYAN * rim_l * 0.95 + MAGENTA * rim_r * 0.85
        lum = min(1, body + 0.6 * max(rim_l, rim_r))
        ch = RAMP[min(len(RAMP) - 1, int(lum * (len(RAMP) - 1) + 0.5))]
        if ch == " ":
            ch = "."
        put(r, c, ch, col * vignette[r, c] ** 0.4, 0.35 * max(rim_l, rim_r))

# -------------------------------------------------------- circuit traces ---
def trace(r, c, steps, dirs, col):
    dr, dc = dirs[0]
    prev = None
    for i in range(steps):
        if random.random() < 0.18 and i > 2:
            ndr, ndc = random.choice(dirs)
            if (ndr, ndc) != (dr, dc) and (ndr, ndc) != (-dr, -dc):
                corner = {((0, 1), (1, 0)): "┐", ((0, -1), (1, 0)): "┌",
                          ((0, 1), (-1, 0)): "┘", ((0, -1), (-1, 0)): "└",
                          ((1, 0), (0, 1)): "└", ((1, 0), (0, -1)): "┘",
                          ((-1, 0), (0, 1)): "┌", ((-1, 0), (0, -1)): "┐"}
                put(r, c, corner.get(((dr, dc), (ndr, ndc)), "+"), col, 0.25)
                dr, dc = ndr, ndc
                r, c = r + dr, c + dc
                continue
        if not (0 <= r < ROWS and 0 <= c < COLS) or hood[r, c] > -0.03 or face[r, c] < 0.03:
            break
        put(r, c, "─" if dr == 0 else "│", col, 0.25)
        prev = (r, c)
        r, c = r + dr, c + dc
    if prev:
        put(prev[0], prev[1], "o", col * 1.4, 0.8)


TRACE = np.array([60, 175, 145], float)
for side in (-1, 1):
    for k in range(4):
        r0 = int(ROWS * 0.76) + k * 2
        c0 = COLS // 2 + side * 13
        trace(r0, c0, random.randint(10, 22), [(0, side), (1, 0), (-1, 0)], TRACE * random.uniform(0.55, 0.9))

# ------------------------------------------------------------------ face ---
for r in range(ROWS):
    for c in range(COLS):
        f = face[r, c]
        if f >= 0:
            continue
        shade = smoothstep(0.0, 0.11, -f) * smoothstep(-0.55, -0.1, Y[r, c])  # hood shadow at top
        if random.random() < 0.22:
            put(r, c, random.choice("01"), np.array([10, 80, 72]) * (0.12 + 0.6 * shade))
        else:
            put(r, c, " ", BG)

# eyes: happy arcs ∩ ∩  (or narrowed, scheming ones... depends who's asking)
EYES = [(-0.12, -0.035), (0.12, -0.035)]
ER, EW, ETH = 0.11, 0.062, 0.019     # big radius + clipped width = gentle curve


def eye_dist(x, y):
    best = 9
    for ex, ey in EYES:
        cy = ey + ER * 0.82                # arc centre sits below the eye
        vx, vy = x - ex, y - cy
        if abs(vx) <= EW and vy < 0:
            d = abs(math.hypot(vx, vy) - ER)
        else:   # rounded end caps
            if vy >= 0 and abs(vx) <= EW:
                best = min(best, 9); continue
            sx = ex + math.copysign(EW, vx)
            sy = cy - math.sqrt(ER * ER - EW * EW)
            d = math.hypot(x - sx, y - sy)
        best = min(best, d)
    return best


half = 1 / ROWS / 2          # half a cell height in normalized units
for r in range(ROWS):
    for c in range(COLS):
        x, y = X[r, c], Y[r, c]
        top = eye_dist(x, y - half / 2) < ETH
        bot = eye_dist(x, y + half / 2) < ETH
        best = eye_dist(x, y)
        if top or bot:
            ch = "█" if top and bot else ("▀" if top else "▄")
            put(r, c, ch, EYE, 0.75)
        elif best < 0.10 and face[r, c] < 0:
            t = 1 - (best - ETH) / (0.10 - ETH)
            if chars[r][c] in "01":
                color[r, c] = np.maximum(color[r, c], CYAN * (0.15 + 0.45 * t * t))
                glow[r, c] = 0.2 * t
            elif t > 0.5 and random.random() < 0.35:
                put(r, c, "·", CYAN * 0.4 * t, 0.1 * t)

# mouth: a blinking cursor. friendly smile, or a prompt awaiting input?
mr, mc = cell_of(0.0, 0.15)
for dc in range(-3, 4):
    put(mr, mc + dc, " ", BG)
for dc in (-1, 0):
    put(mr, mc + dc, "_", np.array([150, 210, 170]), 0.5)

# -------------------------------------------------------- chest terminal ---
lines = [("$ ", "whoami"), ("> ", "[redacted]_")]
w = max(len(a) + len(b) for a, b in lines) + 4
top, left = int(ROWS * 0.78), COLS // 2 - w // 2
FRAME = np.array([40, 140, 130], float)
for r in range(top, top + len(lines) + 2):
    for c in range(left, left + w):
        cellbg[r, c] = [8, 12, 18]
        has_bg[r, c] = True
        edge_r = r in (top, top + len(lines) + 1)
        edge_c = c in (left, left + w - 1)
        if edge_r and edge_c:
            ch = {(top, left): "┌", (top, left + w - 1): "┐"}.get((r, c), "└" if c == left else "┘")
            put(r, c, ch, FRAME, 0.2)
        elif edge_r:
            put(r, c, "─", FRAME, 0.2)
        elif edge_c:
            put(r, c, "│", FRAME, 0.2)
        else:
            put(r, c, " ", BG)
for i, (p, text) in enumerate(lines):
    r = top + 1 + i
    for j, ch in enumerate(p):
        put(r, left + 2 + j, ch, AMBER, 0.6)
    for j, ch in enumerate(text):
        col = GREEN if not text.startswith("[") or ch == "_" else np.array([120, 110, 165])
        put(r, left + 2 + len(p) + j, ch, col, 0.55 if col is GREEN else 0.2)

# ------------------------------------------ dissolve: the edge turns to data
for r in range(ROWS):
    for c in range(COLS):
        d, x = hood[r, c], X[r, c]
        side = smoothstep(0.15, 0.75, x)
        if side <= 0:
            continue
        n = noise[r, c]
        if -0.06 < d < 0.012 and n * side > 0.45:                 # eat the hood edge
            put(r, c, random.choice("01"), MAGENTA * 0.55 * vignette[r, c], 0.25)
        elif 0.012 <= d < 0.28 and random.random() < side * 0.55 * (1 - d / 0.28) ** 1.5:
            t = 1 - d / 0.28
            col = MAGENTA * t + GREEN * (1 - t) * 0.5
            put(r, c, random.choice("01▪·"), col * (0.35 + 0.45 * t) * vignette[r, c], 0.3 * t)

# ---------------------------------------------------------------- glitch ---
GLITCH = {int(ROWS * 0.23): 2}
for r, s in GLITCH.items():
    chars[r] = chars[r][-s:] + chars[r][:-s] if s > 0 else chars[r][-s:] + chars[r][:-s]
    color[r] = np.roll(color[r], s, axis=0)
    glow[r] = np.roll(glow[r], s)

def main():
    # ---------------------------------------------------------------- render ---
    def draw_layer(weight_fn, offset=(0, 0), tint=None):
        img = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
        dr = ImageDraw.Draw(img)
        for r in range(ROWS):
            for c in range(COLS):
                ch = chars[r][c]
                if ch == " ":
                    continue
                wgt = weight_fn(r, c)
                if wgt <= 0:
                    continue
                col = color[r, c] if tint is None else tint
                col = tuple(int(v) for v in np.clip(col * wgt, 0, 255))
                cx = c * CW + CW / 2 + offset[0]
                cy = r * CH + CH / 2 + offset[1]
                dr.text((cx, cy), ch, font=FONT, fill=col, anchor="mm")
        return np.asarray(img, float)


    base = np.ones((SIZE, SIZE, 3)) * BG
    bgimg = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    bd = ImageDraw.Draw(bgimg)
    for r in range(ROWS):
        for c in range(COLS):
            if has_bg[r, c]:
                bd.rectangle([c * CW, r * CH, (c + 1) * CW, (r + 1) * CH], fill=tuple(int(v) for v in cellbg[r, c]))
    bgarr = np.asarray(bgimg, float)
    base = np.where(bgarr.sum(-1, keepdims=True) > 0, bgarr, base)

    text = draw_layer(lambda r, c: 1.0)
    bloom_src = Image.fromarray(draw_layer(lambda r, c: glow[r, c]).astype(np.uint8))
    bloom = (np.asarray(bloom_src.filter(ImageFilter.GaussianBlur(6)), float) * 0.9
             + np.asarray(bloom_src.filter(ImageFilter.GaussianBlur(22)), float) * 0.9)

    # chromatic ghosts on glitched rows
    chroma = np.zeros_like(text)
    g_rows = set(GLITCH)
    chroma += draw_layer(lambda r, c: 0.18 if r in g_rows else 0, (-4, 0), np.array([230, 80, 110]))
    chroma += draw_layer(lambda r, c: 0.18 if r in g_rows else 0, (4, 0), np.array([80, 200, 230]))

    out = base + text + bloom + chroma

    # ambient eye glow wash + CRT scanlines + circular vignette
    yy, xx = np.mgrid[0:SIZE, 0:SIZE] / SIZE * 2 - 1
    for ex, ey in EYES:
        out += CYAN * 0.06 * np.exp(-((xx - ex) ** 2 + (yy - ey) ** 2) / 0.02)[..., None]
    out *= (0.35 + 0.65 * (1 - smoothstep(0.75, 1.25, np.hypot(xx, yy))))[..., None]

    # soft shoulder: highlights roll off instead of clipping to neon
    KNEE = 170.0
    over = np.maximum(out - KNEE, 0)
    out = np.minimum(out, KNEE) + (255 - KNEE) * (1 - np.exp(-over / (255 - KNEE)))
    # pull saturation back a touch
    lum = out @ np.array([0.2126, 0.7152, 0.0722])
    out = lum[..., None] + (out - lum[..., None]) * 0.85

    img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    img.resize((OUT, OUT), Image.LANCZOS).save("ghost_avatar.png", optimize=True)

    # ------------------------------------------------------------------ ANSI ---
    with open("ghost_avatar.ans", "w", encoding="utf-8") as f:
        for r in range(ROWS):
            line = []
            for c in range(COLS):
                R, G, B = (int(v) for v in np.clip(color[r, c], 0, 255))
                line.append(f"\x1b[38;2;{R};{G};{B}m{chars[r][c]}")
            f.write("".join(line) + "\x1b[0m\n")

    print("wrote ghost_avatar.png (%dpx) and ghost_avatar.ans" % OUT)


if __name__ == "__main__":
    main()
