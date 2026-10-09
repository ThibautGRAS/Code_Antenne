"""Rejeu complet d'un enregistrement Cube MEMS AR avec la logique V4 de l'app (portage Python du cœur Swift) :
ArUco (aruco_detector.py) -> centres triangulés -> face -> détection capsules blanches -> rayons -> TrackReconstructor.

Usage :
  python rejouer_complet.py <dossier de l'enregistrement dézippé> <app|all> <dossier de sortie>
    app : face verrouillée quand les 4 ArUco sont mémorisés (comme sur l'iPhone)
    all : face calculée avec toutes les vues des ArUco, puis toutes les images traitées
Réglages : ceux de meta.json, surchargeables par variables d'environnement
  (capsuleDiameterMm, capsuleSizeTolerancePct, planeDeltaCm, planeOffsetCm, minBaselineCm, minRays, maxUncertaintyMm).
Sortie : nombre de micros verts / orange / rouges, face_<mode>.png (vue de face des micros).
"""
import glob
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aruco_detector as AR  # noqa: E402

AR.QUAD_RATIO = 0.85
root = glob.glob(sys.argv[1] + '/*/')[0]
mode = sys.argv[2]
out = sys.argv[3]
frames = [json.loads(l) for l in open(root + 'frames.jsonl', encoding='utf-8') if l.strip()]
meta = json.load(open(root + 'meta.json', encoding='utf-8'))
S = meta['settings']
import os
for k in ('capsuleDiameterMm', 'capsuleSizeTolerancePct', 'planeDeltaCm', 'minBaselineCm', 'minRays', 'maxUncertaintyMm', 'planeOffsetCm'):
    if os.environ.get(k): S[k] = float(os.environ[k])


def m4(v): return np.array(v, float).reshape(4, 4).T
def m3(v): return np.array(v, float).reshape(3, 3).T
def norm(v): return v / np.linalg.norm(v)


def pixel_ray(cam, K, u, v):
    d = cam[:3, :3] @ np.array([(u - K[0, 2]) / K[0, 0], -(v - K[1, 2]) / K[1, 1], -1.0])
    return cam[:3, 3].copy(), norm(d)


# ---------------------------------------------------------------- core port (ReconstructionCore.swift V4)
P = dict(associationRadius=S['associationCm'] / 100, minRays=S['minRays'], minBaseline=S['minBaselineCm'] / 100,
         planeTolerance=S['planeDeltaCm'] / 100, maxResidual=0.02, maxUncertainty=S['maxUncertaintyMm'] / 1000,
         angularNoise=0.0015, outlierGate=0.01, mergeRadius=0.02, maxRaysPerTrack=60,
         associationMaxFrameGap=40, pruneFrameGap=50)


def solve(rays, w=None):
    if len(rays) < 2: return None
    A = np.zeros((3, 3)); b = np.zeros(3); W = 0
    for k, (o, d) in enumerate(rays):
        wk = 1.0 if w is None else w[k]; W += wk
        M = wk * (np.eye(3) - np.outer(d, d)); A += M; b += M @ o
    if abs(np.linalg.det(A)) <= 1e-5 * W ** 3: return None
    inv = np.linalg.inv(A)
    return inv @ b, inv


def perp(o, d, p):
    v = p - o
    return np.linalg.norm(v - d * np.dot(v, d))


def robust(rays):
    s = solve(rays)
    if s is None: return None
    point, inv = s; active = rays
    for _ in range(2):
        dist = np.array([perp(o, d, point) for o, d in active])
        gate = max(P['outlierGate'], 3 * np.sort(dist)[len(dist) // 2])
        kept = [r for r, x in zip(active, dist) if x <= gate]
        if len(kept) >= 2: active = kept
        w = [1 / (P['angularNoise'] * max(0.1, np.linalg.norm(o - point))) ** 2 for o, _ in active]
        s = solve(active, w)
        if s is None: return None
        point, inv = s
    res = np.sqrt(np.mean([perp(o, d, point) ** 2 for o, d in active]))
    return point, res, np.sqrt(max(0, np.trace(inv)))


def baseline(rays):
    O = np.array([o for o, _ in rays])
    return max((np.linalg.norm(a - b) for a in O for b in O), default=0)


class Face:
    def __init__(self, T, w, h, offset):
        self.T, self.w, self.h, self.offset = T, w, h, offset
        self.inv = np.linalg.inv(T)

    def local(self, p): return (self.inv @ np.append(p, 1))[:3]
    def world(self, p): return (self.T @ np.append(p, 1))[:3]

    def intersect(self, o, d, margin=0.10):
        n = self.T[:3, 2]; p0 = self.world([0, 0, self.offset])
        den = np.dot(d, n)
        if abs(den) <= 1e-5: return None
        t = np.dot(p0 - o, n) / den
        if t <= 0: return None
        wp = o + d * t; lp = self.local(wp)
        if abs(lp[0]) > self.w / 2 + margin or abs(lp[1]) > self.h / 2 + margin: return None
        return wp, lp


class Recon:
    def __init__(self): self.tracks = []

    def update(self, obs, frame, face):
        for t in self.tracks: t['seen'] = False
        keys = [(t['local'][:2] if t['state'] == 'confirmed' and t['local'] is not None else t['xy']) for t in self.tracks]
        R = face.inv[:3, :3]
        for o, d, xy in obs:
            lo = face.local(o); ld = norm(R @ d)
            best, bd = -1, np.inf
            for i, t in enumerate(self.tracks):
                if t['seen']: continue
                if t['state'] != 'confirmed' and frame - t['last'] > P['associationMaxFrameGap']: continue
                dist = np.hypot(*(keys[i] - xy))
                if dist < bd: bd, best = dist, i
            if best >= 0 and bd < P['associationRadius']:
                t = self.tracks[best]; t['rays'].append((lo, ld)); t['rays'] = t['rays'][-P['maxRaysPerTrack']:]
                t['xy'] = xy; t['last'] = frame; t['seen'] = True
            else:
                self.tracks.append(dict(rays=[(lo, ld)], xy=xy, last=frame, seen=True, local=None, state='provisional',
                                        res=np.inf, unc=np.inf, depth=np.inf, base=0))
                keys.append(xy)
        self.tracks = [t for t in self.tracks if not (t['state'] != 'confirmed' and frame - t['last'] > P['pruneFrameGap'])]
        for t in self.tracks: self.evaluate(t, face)
        i = 0
        while i < len(self.tracks):
            j = i + 1
            while j < len(self.tracks):
                a, b = self.tracks[i], self.tracks[j]
                if a['state'] != 'confirmed' or a['local'] is None: break
                if b['state'] == 'confirmed' and b['local'] is not None and np.linalg.norm(a['local'] - b['local']) < P['mergeRadius']:
                    a['rays'] = (a['rays'] + b['rays'])[-P['maxRaysPerTrack']:]; a['last'] = max(a['last'], b['last'])
                    self.tracks.pop(j); self.evaluate(a, face)
                else:
                    j += 1
            i += 1

    def evaluate(self, t, face):
        t['base'] = baseline(t['rays'])
        r = robust(t['rays'])
        if r is not None:
            t['local'], t['res'], t['unc'] = r
            t['depth'] = abs(t['local'][2] - face.offset)
        enough = len(t['rays']) >= P['minRays'] and t['base'] >= P['minBaseline']
        if enough and t['unc'] <= P['maxUncertainty'] and t['depth'] <= P['planeTolerance'] and t['res'] <= P['maxResidual']:
            t['state'] = 'confirmed'
        elif enough and t['depth'] > P['planeTolerance'] * 1.5 + 2 * t['unc']:
            t['state'] = 'rejected'
        else:
            t['state'] = 'provisional'


# ---------------------------------------------------------------- white capsule detector (CapsuleDetector.swift port)
def capsules(rgb, thr):
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    h, w = y.shape; st = 4
    ys = np.minimum(h - 1, np.arange(h // st) * st + st // 2); xs = np.minimum(w - 1, np.arange(w // st) * st + st // 2)
    Y, CB, CR = (a[np.ix_(ys, xs)] for a in (y, cb, cr))
    mask = (Y >= int(thr * 255)) & (np.abs(CB - 128) < 24) & (np.abs(CR - 128) < 24)
    lab, _ = ndimage.label(mask); found = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        comp = lab[sl] == i; n = int(comp.sum())
        if n < 2: continue
        bh, bw = comp.shape; dia = max(bw, bh) * st
        if not (6 <= dia <= 100 and 0.42 < bw / max(1, bh) < 2.35 and 0.18 < n / max(1, bw * bh) < 0.98): continue
        cy, cx = ndimage.center_of_mass(comp)
        found.append(((sl[1].start + cx + 0.5) * st, (sl[0].start + cy + 0.5) * st, dia))
    found.sort(key=lambda d: -d[2]); kept = []
    for d in found:
        if all(np.hypot(d[0] - k[0], d[1] - k[1]) >= max(7.0, d[2] * 0.55) for k in kept): kept.append(d)
    return kept


# ---------------------------------------------------------------- markers -> face
def face_from_centers(c):
    p0, p1, p2, p3 = c[0], c[1], c[2], c[3]
    x = norm((p1 + p2) / 2 - (p0 + p3) / 2); y = norm((p0 + p1) / 2 - (p3 + p2) / 2)
    n = norm(np.cross(x, y)); y = norm(np.cross(n, x)); x = norm(np.cross(y, n)); n = norm(np.cross(x, y))
    T = np.eye(4); T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = x, y, n, (p0 + p1 + p2 + p3) / 4
    w = (np.linalg.norm(p0 - p1) + np.linalg.norm(p3 - p2)) / 2; h = (np.linalg.norm(p0 - p3) + np.linalg.norm(p1 - p2)) / 2
    return Face(T, w, h, S['planeOffsetCm'] / 100)


def tri(rs, need_base=0.15):
    if len(rs) < 3 or baseline(rs) < need_base: return None
    s = solve(rs)
    if s is None: return None
    p = s[0]
    return p if np.sqrt(np.mean([perp(o, d, p) ** 2 for o, d in rs])) <= 0.03 else None


images, marker_obs = {}, []
for f in frames:
    rgb = np.asarray(Image.open(root + f['image']).convert('RGB'))
    cam, K = m4(f['camera']), m3(f['intrinsics'])
    for m in AR.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)):
        marker_obs.append((f['index'], m['id'], pixel_ray(cam, K, *m['center'])))

if mode == 'all':
    rays = {}
    for _, i, r in marker_obs: rays.setdefault(i, []).append(r)
    face = face_from_centers({i: tri(rs) for i, rs in rays.items()})
    lock_index = 0
else:
    rays, centers, face, lock_index = {}, {}, None, None
    for idx, i, r in marker_obs:
        rays.setdefault(i, []).append(r); c = tri(rays[i])
        if c is not None: centers[i] = c
        if face is None and len(centers) == 4:
            face = face_from_centers(centers); lock_index = idx
print(f"mode {mode}: face {face.w:.2f} x {face.h:.2f} m, verrouillée à l'image {lock_index}")

rec = Recon()
focal_cache = None
for f in frames:
    if f['index'] < lock_index: continue
    rgb = np.asarray(Image.open(root + f['image']).convert('RGB'))
    cam, K = m4(f['camera']), m3(f['intrinsics'])
    focal = 0.5 * (K[0, 0] + K[1, 1]); world_to_cam = np.linalg.inv(cam)
    obs = []; dets = capsules(rgb, S['whiteThreshold'])
    for u, v, dia in dets:
        o, d = pixel_ray(cam, K, u, v)
        hit = face.intersect(o, d)
        if hit is None: continue
        depth = abs((world_to_cam @ np.append(hit[0], 1))[2])
        expected = focal * (S['capsuleDiameterMm'] / 1000) / depth; tol = S['capsuleSizeTolerancePct'] / 100
        if not (expected * max(0.1, 1 - tol) <= dia <= expected * (1 + tol)): continue
        obs.append((o, d, hit[1][:2]))
    rec.update(obs, f['index'] * 30, face)
    green = sum(t['state'] == 'confirmed' for t in rec.tracks)
    f['_n'] = (len(dets), len(obs), green)

confirmed = [t for t in rec.tracks if t['state'] == 'confirmed']
print(f"détections blanches/image ~{np.median([f['_n'][0] for f in frames if '_n' in f]):.0f}, "
      f"retenues (plan + taille) ~{np.median([f['_n'][1] for f in frames if '_n' in f]):.0f}")
print(f"micros VERTS: {len(confirmed)} / 96 ; orange {sum(t['state']=='provisional' for t in rec.tracks)} ; rouges {sum(t['state']=='rejected' for t in rec.tracks)}")

# top view of the face (local XY) with green points
img = Image.new('RGB', (800, 800), (20, 24, 30)); d = ImageDraw.Draw(img)
sc = 380 / max(face.w, face.h) * 2 / 2
def px(x, y): return 400 + x * sc, 400 - y * sc
d.rectangle([*px(-face.w / 2, face.h / 2), *px(face.w / 2, -face.h / 2)], outline=(80, 200, 120), width=2)
for t in rec.tracks:
    if t['local'] is None: continue
    x, y = px(*t['local'][:2]); col = {'confirmed': (60, 220, 90), 'provisional': (240, 140, 60), 'rejected': (230, 70, 70)}[t['state']]
    r = 5 if t['state'] == 'confirmed' else 3
    d.ellipse([x - r, y - r, x + r, y + r], fill=col)
d.text((10, 10), f"mode {mode}: {len(confirmed)} verts / 96", fill=(255, 255, 255))
img.save(f"{out}/face_{mode}.png")

