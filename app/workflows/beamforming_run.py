# -*- coding: utf-8 -*-
"""
Etape 2 (sous-processus) : beamforming a partir de la CSM en cache.
Lit `<cache_dir>/csm.npz` (etape 1) et ecrit la carte dans `<cache_dir>/bf.npz`.
Se relance vite quand on change la methode / le mesh / les offsets, SANS recharger
le .dat ni recalculer la CSM.

Usage : python app/workflows/beamforming_run.py <params.json>
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
    csm_file = os.path.join(cache_dir, "csm.npz")
    if not os.path.exists(csm_file):
        raise RuntimeError("CSM absente du cache : lancer d'abord l'etape 1 (Charger + CSM).")

    config = Config(overrides={k: v for k, v in params.items() if not k.startswith("_")})

    data = np.load(csm_file)
    f_all = data["f_selected"]
    csm_all = data["CSM"]
    geo = data["geo_positions"]

    # Selection de la bande a traiter DANS la CSM precalculee (aucun recalcul).
    fmin_sel = float(params.get("_fsel_min", float(f_all.min())))
    fmax_sel = float(params.get("_fsel_max", float(f_all.max())))
    if fmax_sel < fmin_sel:
        fmin_sel, fmax_sel = fmax_sel, fmin_sel
    eps = 1e-6
    mask = (f_all >= fmin_sel - eps) & (f_all <= fmax_sel + eps)
    if not mask.any():
        raise RuntimeError(
            f"Aucune frequence de la CSM dans [{fmin_sel:.0f}, {fmax_sel:.0f}] Hz. "
            f"Plage CSM disponible : [{float(f_all.min()):.0f}, {float(f_all.max()):.0f}] Hz "
            f"-> elargis l'etape 1 (plage CSM) ou ajuste la bande.")
    f_sel = f_all[mask]
    csm = csm_all[mask]
    print(f"    {f_sel.size} frequence(s) dans [{fmin_sel:.0f}, {fmax_sel:.0f}] Hz "
          f"(CSM reutilisee, aucun recalcul).", flush=True)

    print("[1/1] Beamforming...", flush=True)
    spl_map, points, grid = beamforming.run_beamforming_pipeline(f_sel, csm, geo, config)

    idx = int(np.argmax(spl_map))
    print(f"    Source estimee : {float(np.max(spl_map)):.2f} dB "
          f"@ {tuple(round(float(v), 3) for v in grid[idx])}", flush=True)

    out = os.path.join(cache_dir, "bf.npz")
    np.savez(out, SPL_map=np.asarray(spl_map), points=np.asarray(points),
             grid_pts=np.asarray(grid), geo_positions=geo,
             fsel=np.array([fmin_sel, fmax_sel], dtype=float))
    print("[OK] Carte de beamforming prete.", flush=True)


if __name__ == "__main__":
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            run(json.load(fh))
    except Exception:
        print("[ERREUR] Etape beamforming echouee :", flush=True)
        traceback.print_exc()
        sys.exit(1)
