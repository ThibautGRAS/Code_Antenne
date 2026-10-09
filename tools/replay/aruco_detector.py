"""Reference implementation (Python) of the app's ArUco detector, Core/ArucoDetector.swift.
DICT_4X4_50, IDs 0-3: adaptive threshold (windows 21 and 31 px), 4-connected dark blobs,
convex hull reduced to a quad, homography, 6x6 cell reading, dictionary match.
`python aruco_detector.py <dossier d'un enregistrement dézippé>` compares it with OpenCV."""
import glob
import json
import sys

import cv2
import numpy as np
from scipy import ndimage

DICT = {  # 6x6 with border, 1 = white, row 0 = top (same as ArucoReferenceFactory.swift)
    0: [[0,0,0,0,0,0],[0,1,0,1,1,0],[0,0,1,0,1,0],[0,0,0,1,1,0],[0,0,0,1,0,0],[0,0,0,0,0,0]],
    1: [[0,0,0,0,0,0],[0,0,0,0,0,0],[0,1,1,1,1,0],[0,1,0,0,1,0],[0,1,0,1,0,0],[0,0,0,0,0,0]],
    2: [[0,0,0,0,0,0],[0,0,0,1,1,0],[0,0,0,1,1,0],[0,0,0,1,0,0],[0,1,1,0,1,0],[0,0,0,0,0,0]],
    3: [[0,0,0,0,0,0],[0,1,0,0,1,0],[0,1,0,0,1,0],[0,0,1,0,0,0],[0,0,1,1,0,0],[0,0,0,0,0,0]],
}
DICT = {k: np.array(v) for k, v in DICT.items()}

RADIUS = 15          # adaptive threshold window = 31 px
OFFSET = 7           # dark if luma < local mean - OFFSET
ERODE = 0            # erosion iterations before labeling (hull is grown back by ERODE px)
QUAD_RATIO = 0.85    # quad area / convex hull area


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def polygon_area(p):
    return 0.5 * abs(sum(p[i][0]*p[(i+1) % len(p)][1] - p[(i+1) % len(p)][0]*p[i][1] for i in range(len(p))))


def reduce_to_quad(hull):
    h = list(hull)
    while len(h) > 4:
        areas = [polygon_area([h[i-1], h[i], h[(i+1) % len(h)]]) for i in range(len(h))]
        h.pop(int(np.argmin(areas)))
    return h


def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u*x, -u*y]); A.append([0, 0, 0, x, y, 1, -v*x, -v*y])
    b = np.array(dst, float).reshape(-1)
    h = np.linalg.solve(np.array(A, float), b)
    return np.append(h, 1).reshape(3, 3)


def apply(H, x, y):
    p = H @ [x, y, 1]
    return p[0]/p[2], p[1]/p[2]


def bilinear(img, x, y):
    x0, y0 = int(np.floor(x)), int(np.floor(y))
    if x0 < 0 or y0 < 0 or x0 + 1 >= img.shape[1] or y0 + 1 >= img.shape[0]:
        return None
    fx, fy = x - x0, y - y0
    return (img[y0, x0]*(1-fx)*(1-fy) + img[y0, x0+1]*fx*(1-fy) + img[y0+1, x0]*(1-fx)*fy + img[y0+1, x0+1]*fx*fy)


def detect_one(img):
    img = img.astype(np.float32)
    h, w = img.shape
    mean = ndimage.uniform_filter(img, size=2*RADIUS+1, mode='nearest')
    dark = img < mean - OFFSET
    if ERODE:
        # Break thin bridges between a marker border and dark background before labeling.
        dark = ndimage.binary_erosion(dark, structure=np.ones((3, 3)), iterations=ERODE)
    labels, n = ndimage.label(dark)
    out = []
    for lab, sl in enumerate(ndimage.find_objects(labels), start=1):
        bh, bw = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if not (18 <= max(bh, bw) <= 400) or min(bh, bw) < 10:
            continue
        comp = labels[sl] == lab
        count = comp.sum()
        if count < 80:
            continue
        # row extremes -> convex hull -> quad
        pts = []
        for r in range(bh):
            cols = np.nonzero(comp[r])[0]
            if len(cols):
                # Pixel (x, y) covers [x-0.5, x+0.5] x [y-0.5, y+0.5] (integer = pixel center, like bilinear).
                x0, x1, yy = sl[1].start + cols[0] - 0.5, sl[1].start + cols[-1] + 0.5, sl[0].start + r
                pts += [(x0, yy - 0.5), (x1, yy - 0.5), (x0, yy + 0.5), (x1, yy + 0.5)]
        if ERODE:
            # Grow the hull back by the eroded margin (pixel corners offset outward).
            pts = [(x + dx, y + dy) for x, y in pts for dx in (-ERODE, ERODE) for dy in (-ERODE, ERODE)]
        hull = convex_hull(pts)
        if len(hull) < 4:
            continue
        hull_area = polygon_area(hull)
        quad = reduce_to_quad(hull)
        quad_area = polygon_area(quad)
        if quad_area < QUAD_RATIO * hull_area or quad_area < 200:
            continue
        sides = [np.hypot(quad[i][0]-quad[(i+1) % 4][0], quad[i][1]-quad[(i+1) % 4][1]) for i in range(4)]
        if min(sides) < 12 or max(sides) / min(sides) > 3:
            continue
        if not (0.3 < count / quad_area < 0.95):
            continue
        for order in (quad, [quad[0], quad[3], quad[2], quad[1]]):
            H = homography([(0, 0), (6, 0), (6, 6), (0, 6)], order)
            grid = np.zeros((6, 6))
            ok = True
            for r in range(6):
                for c in range(6):
                    vals = []
                    for dy in (-0.2, 0, 0.2):
                        for dx in (-0.2, 0, 0.2):
                            x, y = apply(H, c + 0.5 + dx, r + 0.5 + dy)
                            v = bilinear(img, x, y)
                            if v is None:
                                ok = False
                            else:
                                vals.append(v)
                    grid[r, c] = np.mean(vals) if vals else 0
            if not ok:
                break
            lo, hi = grid.min(), grid.max()
            if hi - lo < 30:
                break
            bits = (grid > (lo + hi) / 2).astype(int)
            border = np.r_[bits[0], bits[-1], bits[1:-1, 0], bits[1:-1, -1]]
            if border.sum() > 1:
                break
            found = None
            for mid, pattern in DICT.items():
                for k in range(4):
                    if np.array_equal(np.rot90(bits, -k)[1:-1, 1:-1], pattern[1:-1, 1:-1]):
                        found = (mid, k)
            if found:
                mid, k = found
                corners = [order[(j - k) % 4] for j in range(4)]
                cx, cy = apply(H, 3, 3)
                out.append({'id': mid, 'corners': [tuple(map(float, p)) for p in corners], 'center': (cx, cy)})
                break
    return out


RADII = (10, 15)


def detect(img):
    global RADIUS
    found = {}
    for r in RADII:
        RADIUS = r
        for m in detect_one(img):
            found.setdefault(m['id'], m)
    return [found[k] for k in sorted(found)]


def main():
    root = glob.glob(sys.argv[1] + '/*/')[0]
    frames = [json.loads(l) for l in open(root + 'frames.jsonl', encoding='utf-8') if l.strip()]
    ref = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), cv2.aruco.DetectorParameters())
    tp = fn = fp = 0
    errs = []
    import time
    t = 0
    for f in frames:
        gray = cv2.imread(root + f['image'], cv2.IMREAD_GRAYSCALE)
        t0 = time.time(); mine = detect(gray); t += time.time() - t0
        corners, ids, _ = ref.detectMarkers(gray)
        refs = {int(i): c[0] for c, i in zip(corners, ids.flatten())} if ids is not None else {}
        refs = {k: v for k, v in refs.items() if k <= 3}
        got = {m['id']: m for m in mine}
        for k, c in refs.items():
            if k in got:
                tp += 1
                errs.append(max(np.hypot(*(np.array(got[k]['corners'][j]) - c[j])) for j in range(4)))
            else:
                fn += 1
        fp += len([k for k in got if k not in refs])
    print(f"vs OpenCV: trouvés {tp}, manqués {fn}, en trop {fp}; erreur coin max médiane {np.median(errs) if errs else 0:.2f} px, "
          f"max {max(errs) if errs else 0:.2f} px; {t/len(frames)*1000:.0f} ms/image (python)")


if __name__ == '__main__':
    main()
