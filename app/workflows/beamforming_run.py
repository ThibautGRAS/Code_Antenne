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

    method = str(config.method).lower()
    if method == "obf":
        # OBF : on calcule la carte combinee (toutes les sources) + une carte par
        # source (mode/valeur propre). Tout est mis en cache -> l'UI navigue entre
        # les sources sans recalcul.
        n = int(getattr(config, "n_sources", 1) or 1)
        print(f"[1/1] Beamforming OBF : somme + {n} source(s)...", flush=True)
        config.nmodei = None
        spl0, points, grid = beamforming.run_beamforming_pipeline(f_sel, csm, geo, config)
        maps = [np.asarray(spl0)]
        labels = ["Toutes les sources"]
        for i in range(n):
            config.nmodei = i
            spl_i, _, _ = beamforming.run_beamforming_pipeline(f_sel, csm, geo, config)
            maps.append(np.asarray(spl_i))
            labels.append(f"Source {i + 1}")
            print(f"    source {i + 1}/{n} calculee.", flush=True)
        spl_maps = np.stack(maps)
    else:
        print("[1/1] Beamforming...", flush=True)
        spl0, points, grid = beamforming.run_beamforming_pipeline(f_sel, csm, geo, config)
        spl_maps = np.asarray(spl0)[None, :]
        labels = [method]

    idx = int(np.argmax(spl_maps[0]))
    print(f"    Source estimee (carte combinee) : {float(np.max(spl_maps[0])):.2f} dB "
          f"@ {tuple(round(float(v), 3) for v in grid[idx])}", flush=True)

    out = os.path.join(cache_dir, "bf.npz")
    np.savez(out, SPL_maps=spl_maps, labels=np.array(labels),
             points=np.asarray(points), grid_pts=np.asarray(grid),
             geo_positions=geo, fsel=np.array([fmin_sel, fmax_sel], dtype=float))
    print(f"[OK] {spl_maps.shape[0]} carte(s) prete(s).", flush=True)


if __name__ == "__main__":
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            run(json.load(fh))
    except Exception:
        print("[ERREUR] Etape beamforming echouee :", flush=True)
        traceback.print_exc()
        sys.exit(1)
