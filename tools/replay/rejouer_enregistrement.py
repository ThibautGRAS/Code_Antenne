"""Rejoue un enregistrement de diagnostic Cube MEMS AR (zip exporté depuis l'app).

Pour chaque image : projection de la face verrouillée (rectangle + axes) et des ArUco vus par
ARKit, et détections du détecteur de capsules actuel de l'app (portage Python). Écrit des
images annotées et un résumé, pour vérifier les poses et régler la détection sur PC.

Usage :
  python rejouer_enregistrement.py CubeMEMS_enregistrement_xxx.zip dossier_sortie [--toutes]

Par défaut, une image sur 5 est annotée (--toutes : toutes).
Dépendances : numpy, pillow, scipy.
"""
import io
import json
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def mat4(values):
    return np.array(values, dtype=float).reshape(4, 4).T   # stored column-major


def mat3(values):
    return np.array(values, dtype=float).reshape(3, 3).T


def project(points_world, camera, intrinsics):
    """ARKit convention: camera looks along -Z, X right, Y up; pixels from the top-left, v down."""
    world_to_camera = np.linalg.inv(camera)
    p = np.c_[points_world, np.ones(len(points_world))] @ world_to_camera.T
    depth = -p[:, 2]
    fx, fy, cx, cy = intrinsics[0, 0], intrinsics[1, 1], intrinsics[0, 2], intrinsics[1, 2]
    u = cx + fx * p[:, 0] / depth
    v = cy - fy * p[:, 1] / depth
    return np.c_[u, v], depth


def detect_app(rgb, white_threshold, step=4):
    """Port of CapsuleDetector.swift (white blobs)."""
    r, g, b = [rgb[..., i].astype(np.float32) for i in range(3)]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    h, w = y.shape
    ys = np.minimum(h - 1, np.arange(h // step) * step + step // 2)
    xs = np.minimum(w - 1, np.arange(w // step) * step + step // 2)
    Y, CB, CR = (a[np.ix_(ys, xs)] for a in (y, cb, cr))
    mask = (Y >= int(white_threshold * 255)) & (np.abs(CB - 128) < 24) & (np.abs(CR - 128) < 24)
    labels, _ = ndimage.label(mask)
    found = []
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        comp = labels[sl] == i
        n = int(comp.sum())
        if n < 2:
            continue
        bh, bw = comp.shape
        dia = max(bw, bh) * step
        if not (6 <= dia <= 100 and 0.42 < bw / max(1, bh) < 2.35 and 0.18 < n / max(1, bw * bh) < 0.98):
            continue
        cy_, cx_ = ndimage.center_of_mass(comp)
        found.append(((sl[1].start + cx_ + 0.5) * step, (sl[0].start + cy_ + 0.5) * step, dia))
    found.sort(key=lambda d: -d[2])
    kept = []
    for d in found:
        if all(np.hypot(d[0] - k[0], d[1] - k[1]) >= max(7.0, d[2] * 0.55) for k in kept):
            kept.append(d)
    return kept


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    zip_path, out_dir = sys.argv[1], sys.argv[2]
    every = 1 if '--toutes' in sys.argv else 5

    import os
    os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        root = next(n for n in names if n.endswith('meta.json')).rsplit('meta.json', 1)[0]
        meta = json.loads(archive.read(root + 'meta.json'))
        frames = [json.loads(line) for line in archive.read(root + 'frames.jsonl').decode().splitlines() if line.strip()]
        settings = meta.get('settings', {})
        print(f"{meta.get('app')} — {meta.get('device')} iOS {meta.get('system')} — {len(frames)} images")
        print("Réglages :", json.dumps(settings, ensure_ascii=False))

        travel, previous, rows = 0.0, None, []
        for k, frame in enumerate(frames):
            camera = mat4(frame['camera'])
            position = camera[:3, 3]
            if previous is not None:
                travel += float(np.linalg.norm(position - previous))
            previous = position
            face = mat4(frame['face']) if 'face' in frame else None
            rows.append((frame['index'], frame['tracking'], len(frame.get('markers', {})), face is not None, travel))

            if k % every:
                continue
            try:
                img = Image.open(io.BytesIO(archive.read(root + frame['image']))).convert('RGB')
            except KeyError:
                continue
            intrinsics = mat3(frame['intrinsics'])
            draw = ImageDraw.Draw(img)

            detections = detect_app(np.asarray(img), settings.get('whiteThreshold', 0.82))
            for x, y, dia in detections:
                rr = max(5, dia / 2)
                draw.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(255, 0, 255), width=3)

            if face is not None:
                w, h = frame['faceSize']
                offset = frame.get('planeOffset', 0.0)
                corners = np.array([[-w / 2, h / 2, 0], [w / 2, h / 2, 0], [w / 2, -h / 2, 0], [-w / 2, -h / 2, 0]])
                world = (np.c_[corners, np.ones(4)] @ face.T)[:, :3]
                uv, depth = project(world, camera, intrinsics)
                if (depth > 0).all():
                    draw.line([tuple(p) for p in uv] + [tuple(uv[0])], fill=(0, 255, 0), width=4)
                axes = np.array([[0, 0, 0], [0.3, 0, 0], [0, 0.3, 0], [0, 0, 0.3], [0, 0, offset]])
                uv, depth = project((np.c_[axes, np.ones(5)] @ face.T)[:, :3], camera, intrinsics)
                if (depth > 0).all():
                    for i, color in zip((1, 2, 3), ((255, 0, 0), (0, 255, 0), (0, 128, 255))):
                        draw.line([tuple(uv[0]), tuple(uv[i])], fill=color, width=5)

            for marker_id, values in frame.get('markers', {}).items():
                m = mat4(values)
                uv, depth = project(m[:3, 3][None, :], camera, intrinsics)
                if depth[0] > 0:
                    u, v = uv[0]
                    draw.rectangle([u - 14, v - 14, u + 14, v + 14], outline=(0, 255, 255), width=4)
                    draw.text((u + 18, v - 10), f"ID{marker_id}", fill=(0, 255, 255))

            draw.text((20, 20), f"#{frame['index']} {frame['tracking']} - {len(detections)} detections app",
                      fill=(255, 255, 0))
            img.save(f"{out_dir}/{frame['index']:06d}.jpg", quality=80)

    with open(f"{out_dir}/resume.csv", 'w', encoding='utf-8') as f:
        f.write("index;tracking;arucos_vus;face_verrouillee;distance_parcourue_m\n")
        for row in rows:
            f.write(f"{row[0]};{row[1]};{row[2]};{int(row[3])};{row[4]:.2f}\n")
    print(f"Images annotées et resume.csv dans {out_dir} (vert = face, cyan = ArUco ARKit, violet = détections app)")


if __name__ == '__main__':
    main()
