"""App icon for Cube MEMS AR: isometric cube, capsule grid on the front face,
validated (green) microphones, AR corner brackets, scan line. 1024x1024, opaque."""
import math
import sys

from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1]
S = 4                      # supersampling
N = 1024 * S

def rgba(hex_color, a=255):
    h = hex_color.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

# ---------------------------------------------------------------- background
bg = Image.new('RGBA', (N, N))
top, bottom = rgba('#0A1220'), rgba('#0B3A48')
px = bg.load()
for y in range(N):
    for x in range(0, N):
        t = min(1.0, max(0.0, (0.35 * x + 0.65 * y) / N))
        px[x, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)

glow = Image.new('RGBA', (N, N), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse([N * 0.18, N * 0.2, N * 0.82, N * 0.86], fill=rgba('#39C5CF', 70))
bg = Image.alpha_composite(bg, glow.filter(ImageFilter.GaussianBlur(N * 0.12)))

# ---------------------------------------------------------------- isometric cube
cx, cy, s = N * 0.5, N * 0.515, N * 0.165
c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))

def P(x, y, z):
    return (cx + (x - z) * c30 * s, cy - y * s + (x + z) * s30 * s)

faces = Image.new('RGBA', (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(faces)
# Visible faces: top (y=+1), left/front (z=+1), right (x=+1).
d.polygon([P(-1, 1, -1), P(1, 1, -1), P(1, 1, 1), P(-1, 1, 1)], fill=rgba('#1C3A4E', 235))
d.polygon([P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1)], fill=rgba('#11283A', 245))
d.polygon([P(1, -1, 1), P(1, -1, -1), P(1, 1, -1), P(1, 1, 1)], fill=rgba('#0D1E2C', 245))

# Net on the right face.
net = rgba('#39C5CF', 55)
for k in range(1, 6):
    t = -1 + 2 * k / 6
    d.line([P(1, -1, t), P(1, 1, t)], fill=net, width=S * 2)
    d.line([P(1, t, 1), P(1, t, -1)], fill=net, width=S * 2)

# Edges.
edge = rgba('#7FE7EF', 230)
w = int(S * 5)
for a, b in [((-1, 1, -1), (1, 1, -1)), ((1, 1, -1), (1, 1, 1)), ((1, 1, 1), (-1, 1, 1)), ((-1, 1, 1), (-1, 1, -1)),
             ((-1, -1, 1), (1, -1, 1)), ((1, -1, 1), (1, -1, -1)), ((-1, -1, 1), (-1, 1, 1)),
             ((1, -1, 1), (1, 1, 1)), ((1, -1, -1), (1, 1, -1))]:
    d.line([P(*a), P(*b)], fill=edge, width=w, joint='curve')
bg = Image.alpha_composite(bg, faces)

# ---------------------------------------------------------------- capsule grid on the front face (z=+1)
dots = Image.new('RGBA', (N, N), (0, 0, 0, 0))
glows = Image.new('RGBA', (N, N), (0, 0, 0, 0))
dd, gd = ImageDraw.Draw(dots), ImageDraw.Draw(glows)
grid = 4
green = {(0, 0), (0, 1), (0, 2), (0, 3), (1, 0), (1, 1), (1, 2), (2, 0)}   # scanned so far: from bottom-right
r = N * 0.019
for col in range(grid):            # col 0 = rightmost column (x near +1)
    for row in range(grid):        # row 0 = bottom
        x = 0.75 - 1.5 * col / (grid - 1)
        y = -0.75 + 1.5 * row / (grid - 1)
        X, Y = P(x, y, 1)
        if (col, row) in green:
            gd.ellipse([X - r * 1.9, Y - r * 1.9, X + r * 1.9, Y + r * 1.9], fill=rgba('#3FB950', 120))
            dd.ellipse([X - r, Y - r, X + r, Y + r], fill=rgba('#56D364'))
            dd.ellipse([X - r * 0.4, Y - r * 0.55, X + r * 0.15, Y - r * 0.05], fill=rgba('#C8F7D0', 200))
        else:
            dd.ellipse([X - r * 0.85, Y - r * 0.85, X + r * 0.85, Y + r * 0.85], fill=rgba('#E6EDF3', 235))
bg = Image.alpha_composite(bg, glows.filter(ImageFilter.GaussianBlur(N * 0.010)))
bg = Image.alpha_composite(bg, dots)

# ---------------------------------------------------------------- scan line across the front face
scan = Image.new('RGBA', (N, N), (0, 0, 0, 0))
sd = ImageDraw.Draw(scan)
yline = 0.12
sd.line([P(-1.0, yline, 1), P(1.0, yline, 1)], fill=rgba('#39C5CF', 255), width=int(S * 6))
scan_glow = scan.filter(ImageFilter.GaussianBlur(N * 0.012))
bg = Image.alpha_composite(bg, scan_glow)
bg = Image.alpha_composite(bg, scan_glow)
bg = Image.alpha_composite(bg, scan)

# ---------------------------------------------------------------- AR corner brackets
br = Image.new('RGBA', (N, N), (0, 0, 0, 0))
bd = ImageDraw.Draw(br)
m, L, t = N * 0.15, N * 0.10, int(N * 0.016)
col = rgba('#E6EDF3', 235)
for (x0, y0, sx, sy) in [(m, m, 1, 1), (N - m, m, -1, 1), (m, N - m, 1, -1), (N - m, N - m, -1, -1)]:
    bd.line([(x0, y0 + sy * L), (x0, y0), (x0 + sx * L, y0)], fill=col, width=t, joint='curve')
    bd.ellipse([x0 - t / 2, y0 - t / 2, x0 + t / 2, y0 + t / 2], fill=col)
    for (ex, ey) in [(x0, y0 + sy * L), (x0 + sx * L, y0)]:
        bd.ellipse([ex - t / 2, ey - t / 2, ex + t / 2, ey + t / 2], fill=col)
bg = Image.alpha_composite(bg, br)

icon = bg.convert('RGB').resize((1024, 1024), Image.LANCZOS)
icon.save(OUT, 'PNG')
icon.resize((180, 180), Image.LANCZOS).save(OUT.replace('.png', '_180.png'), 'PNG')
print('saved', OUT)
