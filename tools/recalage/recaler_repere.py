"""Recale un export Cube MEMS AR dans le repère réel de l'antenne.

L'app exporte les micros dans le repère de la face (origine au centre des 4 ArUco,
X droite, Y haut, Z vers l'opérateur). Ce script calcule le déplacement rigide
(rotation + translation, sans mise à l'échelle) qui amène des micros de référence,
dont on connaît la position réelle, sur ces positions, puis l'applique à tous les micros.

  - 3 références ou plus (non alignées) : rotation + translation par moindres carrés
    (méthode de Kabsch). Idéal : les 4 micros des coins de la face.
  - 1 référence : translation seule (suppose les axes de la face déjà alignés sur le
    repère réel) ; à éviter, une petite rotation des ArUco n'est pas corrigée.

Usage :
  python recaler_repere.py export_96mu.csv references.csv sortie.csv

  export_96mu.csv : fichier "..._<N>mu.csv" (X;Y;Z, une ligne par voie, voie 1 en premier)
                    ou "..._details.csv" de l'app.
  references.csv  : num;X;Y;Z  (numéro de voie et position réelle en mètres), par ex.
                        num;X;Y;Z
                        1;0.935;0.120;1.450
                        12;0.935;1.880;1.450
                        85;-0.935;0.120;1.450
                        96;-0.935;1.880;1.450
  sortie.csv      : X;Y;Z dans le repère réel, même ordre de voies (format data_geo).
"""
import csv
import sys

import numpy as np


def read_export(path):
    """Positions (N×3) in channel order, from a geometry or a details export."""
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
    if not rows:
        sys.exit(f"{path} : fichier vide")
    if 'X_m' in rows[0]:
        rows.sort(key=lambda r: int(r['num']))
        return np.array([[float(r['X_m']), float(r['Y_m']), float(r['Z_m'])] for r in rows])
    return np.array([[float(r['X']), float(r['Y']), float(r['Z'])] for r in rows])


def read_references(path):
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
    return {int(r['num']): np.array([float(r['X']), float(r['Y']), float(r['Z'])]) for r in rows}


def rigid_fit(source, target):
    """R, t minimizing Σ|R·source + t − target|² (proper rotation, no scale)."""
    source_center = source.mean(axis=0)
    target_center = target.mean(axis=0)
    h = (source - source_center).T @ (target - target_center)
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    rotation = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    return rotation, target_center - rotation @ source_center


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    export_path, references_path, output_path = sys.argv[1:]

    points = read_export(export_path)
    references = read_references(references_path)

    missing = [n for n in references if not 1 <= n <= len(points)]
    if missing:
        sys.exit(f"Voies de référence absentes de l'export ({len(points)} micros) : {missing}")

    numbers = sorted(references)
    source = np.array([points[n - 1] for n in numbers])
    target = np.array([references[n] for n in numbers])

    if len(numbers) >= 3:
        if np.linalg.matrix_rank(source - source.mean(axis=0), tol=1e-3) < 2:
            sys.exit("Les références sont alignées : prendre au moins 3 micros non alignés (ex. les 4 coins).")
        rotation, translation = rigid_fit(source, target)
        mode = f"rotation + translation ({len(numbers)} références)"
    elif len(numbers) == 1:
        rotation = np.eye(3)
        translation = target[0] - source[0]
        mode = "translation seule (1 référence) : axes supposés déjà alignés"
    else:
        sys.exit("2 références ne suffisent pas à fixer la rotation : en donner 1 (translation seule) ou au moins 3.")

    moved = points @ rotation.T + translation

    print(f"Recalage : {mode}")
    angle = np.degrees(np.arccos(np.clip((np.trace(rotation) - 1) / 2, -1, 1)))
    print(f"  rotation appliquée : {angle:.2f}°   translation : {np.round(translation, 4)} m")
    # Face microphones are nearly coplanar: check that the face normal ends up on the right side.
    print(f"  axe Z de la face (vers l'opérateur) dans le repère réel : {np.round(rotation @ [0, 0, 1], 3)}"
          " -> doit pointer vers l'extérieur du cube")
    print("  écart sur les références (mm) :")
    for n in numbers:
        error = np.linalg.norm(moved[n - 1] - references[n]) * 1000
        print(f"    voie {n:3d} : {error:6.1f}")
    if len(numbers) >= 3:
        rms = np.sqrt(np.mean(np.sum((moved[[n - 1 for n in numbers]] - target) ** 2, axis=1))) * 1000
        print(f"  RMS : {rms:.1f} mm  (un écart > ~10 mm signale une erreur de numérotation ou de scan)")

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        f.write("X;Y;Z\n")
        for x, y, z in moved:
            f.write(f"{x:.5f};{y:.5f};{z:.5f}\n")
    print(f"Écrit : {output_path} ({len(moved)} micros)")


if __name__ == '__main__':
    main()
