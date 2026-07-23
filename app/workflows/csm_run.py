# -*- coding: utf-8 -*-
"""
Etape 1 (sous-processus) : charge le .dat + calcule la CSM, met (f, CSM, geo) en
cache (`<cache_dir>/csm.npz`). C'est le coeur couteux (I/O + FFT) : on ne le refait
que si les donnees ou les frequences changent.

Usage : python app/workflows/csm_run.py <params.json>
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
    from src import read_info, signal_process

    cache_dir = params["_cache_dir"]
    config = Config(overrides={k: v for k, v in params.items() if not k.startswith("_")})

    print("[1/2] Chargement des donnees...", flush=True)
    read_info.load_band_corrections(config)
    raw_data, config = read_info.load_validation_data(config)
    geo = np.asarray(read_info.load_geo_positions(config))

    print("[2/2] Calcul de la CSM (FFT sur les frequences)...", flush=True)
    sigs = signal_process.extract_mic_signals(raw_data, config)
    f_sel, csm = signal_process.MIScalc(sigs, config)
    f_sel = np.asarray(f_sel)
    csm = np.asarray(csm)

    out = os.path.join(cache_dir, "csm.npz")
    np.savez(out, f_selected=f_sel, CSM=csm, geo_positions=geo)
    print(f"[OK] CSM prete : {f_sel.size} frequence(s), {geo.shape[0]} micros.", flush=True)


if __name__ == "__main__":
    try:
        with open(sys.argv[1], "r", encoding="utf-8") as fh:
            run(json.load(fh))
    except Exception:
        print("[ERREUR] Etape CSM echouee :", flush=True)
        traceback.print_exc()
        sys.exit(1)
