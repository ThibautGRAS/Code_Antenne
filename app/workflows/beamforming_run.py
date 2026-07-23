# -*- coding: utf-8 -*-
"""
Execution HEADLESS du beamforming cube, lancee en sous-processus par l'appli
(app/runner.py). Equivalent GUI de main_BEAMFORMING_cube.py :
  1. lit les parametres depuis un JSON,
  2. construit Config(overrides=...),
  3. appelle les fonctions de src/ (AUCUNE logique dupliquee),
  4. ouvre la visualisation (pyvista / matplotlib).

Usage :  python app/workflows/beamforming_run.py <params.json>
"""

import os
import sys
import json
import traceback

# Racine du depot (app/workflows/ -> app/ -> racine), pour que `data`/`src`
# soient importables meme sans `pip install -e .`.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def run(params):
    import numpy as np
    from data.config import Config
    from src import read_info, signal_process, beamforming

    config = Config(overrides=params)

    print("[1/3] Chargement des donnees...", flush=True)
    read_info.load_band_corrections(config)
    raw_data, config = read_info.load_validation_data(config)
    geo_positions = read_info.load_geo_positions(config)

    print("[2/3] Calcul CSM + beamforming...", flush=True)
    sigs = signal_process.extract_mic_signals(raw_data, config)
    f_sel, csm = signal_process.MIScalc(sigs, config)
    spl_map, points, grid_pts = beamforming.run_beamforming_pipeline(
        f_sel, csm, geo_positions, config)

    idx = int(np.argmax(spl_map))
    print(f"    Source estimee : {float(np.max(spl_map)):.2f} dB "
          f"@ {tuple(round(float(v), 3) for v in grid_pts[idx])}", flush=True)

    print("[3/3] Ouverture de la visualisation "
          "(fermer la fenetre pour terminer)...", flush=True)
    plotter = beamforming.plot_beamforming(
        cfg=config, SPL_values=spl_map, points=points,
        coordinates_list=grid_pts, show_spheres=False, geo_positions=geo_positions)
    title = (f"BEAMFORMING - fmin={config.fmin_bf:.0f} Hz, "
             f"fmax={config.fmax_bf:.0f} Hz")
    plotter.show(title=title)
    print("[OK] Termine.", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("[ERREUR] usage: beamforming_run.py <params.json>", flush=True)
        sys.exit(2)
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            _params = json.load(fh)
        run(_params)
    except Exception:
        print("[ERREUR] Le calcul a echoue :", flush=True)
        traceback.print_exc()
        sys.exit(1)
