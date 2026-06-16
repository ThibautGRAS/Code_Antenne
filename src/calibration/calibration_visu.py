# -*- coding: utf-8 -*-
"""
Created on Tue Apr  7 15:34:40 2026

@author: gras
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats

def plot_calibration_pair(pair_result):
    

    plt.figure(figsize=(8, 4))
    plt.plot(pair_result["bands"], pair_result["spl_micro"], 'b-o', label="Micro")
    plt.plot(pair_result["bands"], pair_result["spl_mems"], 'r-o', label="MEMS")
    plt.xscale("log")
    plt.xlabel("Fréquence centrale (Hz)")
    plt.ylabel("SPL (dB)")
    plt.title(
        f"Fichier {pair_result['file_number']} : "
        f"Micro {pair_result['micro_channel']} ↔ MEMS {pair_result['mems_channel']}"
    )
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()
    



def same_grid(b1, b2, rtol=1e-8, atol=1e-10):
    return b1.shape == b2.shape and np.allclose(b1, b2, rtol=rtol, atol=atol)


def normality_test_values(values):
    values = np.asarray(values)
    values = values[np.isfinite(values)]

    if len(values) < 3:
        return False, np.nan

    if len(values) <= 5000:
        stat, pval = stats.shapiro(values)
    else:
        vals_std = (values - np.mean(values)) / max(np.std(values, ddof=1), 1e-12)
        stat, pval = stats.kstest(vals_std, "norm")

    return pval > 0.05, pval


def mean_ic95(arr):
    arr = np.asarray(arr)
    if arr.ndim != 2 or arr.shape[0] == 0:
        return np.array([]), np.array([])

    mean_val = np.mean(arr, axis=0)
    std_val = np.std(arr, axis=0, ddof=1) if arr.shape[0] > 1 else np.zeros(arr.shape[1])

    if arr.shape[0] > 1:
        tval = stats.t.ppf(0.975, df=arr.shape[0] - 1)
        ic95 = tval * std_val / np.sqrt(arr.shape[0])
    else:
        ic95 = np.zeros(arr.shape[1])

    return mean_val, ic95


def prediction_ip95(arr):
    arr = np.asarray(arr)
    if arr.ndim != 2 or arr.shape[0] == 0:
        return np.array([]), np.array([])

    mean_val = np.mean(arr, axis=0)
    std_val = np.std(arr, axis=0, ddof=1) if arr.shape[0] > 1 else np.zeros(arr.shape[1])

    if arr.shape[0] > 1:
        tval = stats.t.ppf(0.975, df=arr.shape[0] - 1)
        ip95 = tval * std_val * np.sqrt(1 + 1 / arr.shape[0])
    else:
        ip95 = np.zeros(arr.shape[1])

    return mean_val, ip95


def plot_calibration_pair(pair_result):
    plt.figure(figsize=(8, 4))
    plt.plot(pair_result["bands"], pair_result["spl_micro"], 'b-o', label="Micro")
    plt.plot(pair_result["bands"], pair_result["spl_mems"], 'r-o', label="MEMS")
    plt.xscale("log")
    plt.xlabel("Fréquence centrale (Hz)")
    plt.ylabel("SPL (dB)")
    plt.title(
        f"Fichier {pair_result['file_number']} : "
        f"Micro {pair_result['micro_channel']} ↔ MEMS {pair_result['mems_channel']}"
    )
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()


def run_post_from_csv(out_folder, base_name, unit="dB"):
    """
    Recharge les CSV *_bands_pa.csv et génère les tracés globaux de post-traitement.
    """
    csv_files = sorted(out_folder.glob(f"{base_name}*_bands_pa.csv"))
    print(f"\n📂 Relecture {len(csv_files)} fichiers CSV pour post-traitement")

    if len(csv_files) == 0:
        raise FileNotFoundError(f"Aucun CSV trouvé dans {out_folder}")

    all_diffs = []
    micro_levels_all = []
    mems_levels_all = []
    all_bands = None

    for csv_path in csv_files:
        dpd = pd.read_csv(csv_path)

        pairs = dpd[["micro_channel", "mems_channel"]].drop_duplicates()

        for _, pair in pairs.iterrows():
            micro_ch = int(pair["micro_channel"])
            mems_ch = int(pair["mems_channel"])

            dpd_pair = dpd[
                (dpd["micro_channel"] == micro_ch) &
                (dpd["mems_channel"] == mems_ch)
            ].sort_values("band_center_Hz")

            bands = dpd_pair["band_center_Hz"].values
            micro_pa = dpd_pair["micro_pa"].values
            mems_pa = dpd_pair["mems_pa"].values

            micro_db = 20 * np.log10(np.maximum(micro_pa, 1e-30) / 2e-5)
            mems_db = 20 * np.log10(np.maximum(mems_pa, 1e-30) / 2e-5)
            diff = mems_db - micro_db

            if all_bands is None:
                all_bands = bands
            elif not same_grid(all_bands, bands):
                print(f"⚠️ Grille différente dans {csv_path.name} pour paire {micro_ch}-{mems_ch}")

            all_diffs.append(diff)
            micro_levels_all.append(micro_pa)
            mems_levels_all.append(mems_pa)

    if all_bands is None:
        raise RuntimeError("Aucune bande détectée lors de la relecture CSV.")

    micro_arr = np.vstack(micro_levels_all) if len(micro_levels_all) > 0 else np.empty((0, len(all_bands)))
    mems_arr = np.vstack(mems_levels_all) if len(mems_levels_all) > 0 else np.empty((0, len(all_bands)))
    all_diffs = np.vstack(all_diffs) if len(all_diffs) > 0 else np.empty((0, len(all_bands)))

    print(f"\n=== Normalité : {micro_arr.shape[0]} mesures micro, {mems_arr.shape[0]} mesures MEMS, sur {all_bands.size} bandes ===")

    if unit == "Pa":
        arr_micro = micro_arr
        arr_mems = mems_arr
        title = "Normalité par bande — domaine linéaire (Pa)"
    elif unit == "dB":
        arr_micro = 20 * np.log10(np.maximum(micro_arr, 1e-30) / 2e-5)
        arr_mems = 20 * np.log10(np.maximum(mems_arr, 1e-30) / 2e-5)
        title = "Normalité par bande — domaine dB SPL"
    else:
        raise ValueError("unit doit être 'Pa' ou 'dB'")

    p_micro = []
    p_mems = []

    for ib in range(len(all_bands)):
        vals_mic = arr_micro[:, ib] if arr_micro.size else np.array([])
        vals_mem = arr_mems[:, ib] if arr_mems.size else np.array([])

        _, pval_mic = normality_test_values(vals_mic)
        _, pval_mem = normality_test_values(vals_mem)

        p_micro.append(pval_mic)
        p_mems.append(pval_mem)

    plt.figure(figsize=(9, 4))
    plt.semilogx(all_bands, p_micro, 'o-', label=f"Micro ({unit})")
    plt.semilogx(all_bands, p_mems, 's-', label=f"MEMS ({unit})")
    plt.axhline(0.05, color='gray', ls='--', label='p = 0.05')
    plt.xlabel("Fréquence centrale (Hz)")
    plt.ylabel("p-value test normalité")
    plt.xlim([20, 25000])
    plt.ylim([-0.02, 1.02])
    plt.title(title)
    plt.legend()
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.tight_layout()
    plt.show()

    mean_diff_ic, ic95_diff = mean_ic95(all_diffs)
    mean_diff, ip95_diff = prediction_ip95(all_diffs)

    plt.figure(figsize=(9, 5))
    for diff in all_diffs:
        plt.plot(all_bands, diff, marker='o', linestyle='None',
                 markersize=4, alpha=0.25, color='blue')

    plt.fill_between(all_bands, mean_diff_ic - ic95_diff, mean_diff_ic + ic95_diff,
                     color='gray', alpha=0.3, label='IC95%')
    plt.plot(all_bands, mean_diff_ic, 'k-o', label='Δ Niveau moyen (MEMS - Micro)')
    plt.xscale("log")
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.xlabel("Fréquence centrale (Hz)")
    plt.ylabel("Δ Niveau (dB SPL)")
    plt.title("Différence moyenne MEMS - Micro (±IC95%)")
    plt.xticks(all_bands, [str(int(f)) for f in all_bands], rotation=45, fontsize=8)
    plt.xlim([20, 25000])
    plt.ylim([-20, 35])
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(9, 5))
    for diff in all_diffs:
        plt.plot(all_bands, diff, marker='o', linestyle='None',
                 markersize=4, alpha=0.25, color='blue')

    plt.fill_between(all_bands, mean_diff - ip95_diff, mean_diff + ip95_diff,
                     color='gray', alpha=0.3, label='IP95%')
    plt.plot(all_bands, mean_diff, 'k-o', label='Δ Niveau moyen (MEMS - Micro)')
    plt.xscale("log")
    plt.grid(True, which="both", ls="--", lw=0.5)
    plt.xlabel("Fréquence centrale (Hz)")
    plt.ylabel("Δ Niveau (dB SPL)")
    plt.title("Différence moyenne MEMS - Micro (±IP95%)")
    plt.xticks(all_bands, [str(int(f)) for f in all_bands], rotation=45, fontsize=8)
    plt.xlim([20, 25000])
    plt.ylim([-20, 35])
    plt.legend()
    plt.tight_layout()
    plt.show()

    return {
        "bands": all_bands,
        "micro_arr": micro_arr,
        "mems_arr": mems_arr,
        "all_diffs": all_diffs
    }