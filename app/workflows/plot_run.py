# -*- coding: utf-8 -*-
"""
Etape 3 (sous-processus) : affiche la carte de beamforming en cache.
Lit `<cache_dir>/bf.npz` (etape 2) et ouvre la visualisation (pyvista/matplotlib).

Usage : python app/workflows/plot_run.py <params.json>
"""

import os
import sys
import json
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def run(params):
    import numpy as np
    from data.config import Config
    from src import beamforming

    cache_dir = params["_cache_dir"]
    bf_file = os.path.join(cache_dir, "bf.npz")
    if not os.path.exists(bf_file):
        raise RuntimeError("Carte absente du cache : lancer d'abord l'etape 2 (Beamforming).")

    config = Config(overrides={k: v for k, v in params.items() if not k.startswith("_")})

    data = np.load(bf_file)
    spl_map = data["SPL_map"]
    points = data["points"]
    grid = data["grid_pts"]
    geo = data["geo_positions"]
    fsel = data["fsel"] if "fsel" in data.files else None

    print("[1/1] Ouverture de la visualisation "
          "(fermer la fenetre pour terminer)...", flush=True)
    plotter = beamforming.plot_beamforming(
        cfg=config, SPL_values=spl_map, points=points,
        coordinates_list=grid, show_spheres=False, geo_positions=geo)
    if fsel is not None:
        title = f"BEAMFORMING [{float(fsel[0]):.0f}-{float(fsel[1]):.0f} Hz]"
    else:
        title = f"BEAMFORMING - fmin={config.fmin_bf:.0f} Hz, fmax={config.fmax_bf:.0f} Hz"
    plotter.show(title=title)
    print("[OK] Termine.", flush=True)


if __name__ == "__main__":
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            run(json.load(fh))
    except Exception:
        print("[ERREUR] Etape affichage echouee :", flush=True)
        traceback.print_exc()
        sys.exit(1)
