# -*- coding: utf-8 -*-
"""
Calibration MEMS / microphones de référence
"""

import numpy as np
import pandas as pd
from scipy import stats

from src.signal_process import compute_all_channels_spectra
from .calibration_visu import plot_calibration_pair


def process_calibration_file(
    Sigs_val,
    micros_dict,
    corr_map,
    config,
    file_number=None,
    window_type="hann"
):
    """
    Traite un fichier complet de calibration MEMS / micros de référence.
    """
    rows = []
    pair_results = []

    # ============================================================
    # 1) Préparation micros de référence
    # ============================================================
    micro_channels = [ch for ch in corr_map.keys() if ch in micros_dict]

    if len(micro_channels) == 0:
        raise ValueError(f"Aucun micro de référence valide pour le fichier {file_number}.")

    fs_micro_set = {micros_dict[ch]["fs"] for ch in micro_channels}
    if len(fs_micro_set) != 1:
        raise ValueError(
            f"Les fréquences d'échantillonnage des micros diffèrent pour le fichier {file_number}."
        )
    fs_micro = list(fs_micro_set)[0]

    min_len_micro = min(len(micros_dict[ch]["signal"]) for ch in micro_channels)

    micro_signals = np.array([
        micros_dict[ch]["signal"][:min_len_micro]
        for ch in micro_channels
    ])

    micro_results = compute_all_channels_spectra(
        signals=micro_signals,
        fs=fs_micro,
        df_band=config.df_band,
        tmin=config.tmin,
        tmax=config.tmax,
        window_type=window_type,
        input_in_pa=True,
        smems=None,
        apply_band_correction=False,
        bands_corr=None,
        diff_corr=None,
        channel_ids=micro_channels,
        fmin=1.0,
        fmax=min(fs_micro, config.Fe) / 2
    )

    # ============================================================
    # 2) Préparation MEMS
    # ============================================================
    mems_channels = [
        mems_ch for mems_ch in corr_map.values()
        if mems_ch < Sigs_val.shape[0]
    ]

    if len(mems_channels) == 0:
        raise ValueError(f"Aucun MEMS valide pour le fichier {file_number}.")

    mems_signals = np.array([
        Sigs_val[mems_ch, :]
        for mems_ch in mems_channels
    ])

    mems_results = compute_all_channels_spectra(
        signals=mems_signals,
        fs=config.Fe,
        df_band=config.df_band,
        tmin=config.tmin,
        tmax=config.tmax,
        window_type=window_type,
        input_in_pa=False,
        smems=config.SMEMS,
        apply_band_correction=False,
        bands_corr=None,
        diff_corr=None,
        channel_ids=mems_channels,
        fmin=1.0,
        fmax=min(fs_micro, config.Fe) / 2
    )

    # ============================================================
    # 3) Comparaison paire par paire
    # ============================================================
    for micro_ch, mems_ch in corr_map.items():

        if micro_ch not in micro_results:
            print(f"⚠️ Micro {micro_ch} absent des résultats pour le fichier {file_number}.")
            continue

        if mems_ch not in mems_results:
            print(f"⚠️ MEMS {mems_ch} absent des résultats pour le fichier {file_number}.")
            continue

        pair_core = compute_calibration_pair_from_results(
            micro_results[micro_ch],
            mems_results[mems_ch]
        )

        pair_result = {
            "file_number": file_number,
            "micro_channel": micro_ch,
            "mems_channel": mems_ch,
            **pair_core
        }
        pair_results.append(pair_result)

        for fc, lm, lmems, sm, sM, dd in zip(
            pair_result["bands"],
            pair_result["levels_micro"],
            pair_result["levels_mems"],
            pair_result["spl_micro"],
            pair_result["spl_mems"],
            pair_result["diff_db"]
        ):
            rows.append({
                "file_number": int(file_number) if file_number is not None else -1,
                "micro_channel": int(micro_ch),
                "mems_channel": int(mems_ch),
                "band_center_Hz": float(fc),
                "micro_pa": float(lm),
                "mems_pa": float(lmems),
                "micro_dB": float(sm),
                "mems_dB": float(sM),
                "diff_db": float(dd)
            })

    df_long = pd.DataFrame(rows)

    print(f"[OK] Fichier {file_number} traité : {len(pair_results)} paires valides.")
    return pair_results, df_long

def compute_calibration_pair_from_results(micro_result, mems_result):
    """
    Compare les résultats spectraux d'une paire micro / MEMS.
    """
    bands_micro = micro_result["bands"]
    bands_mems = mems_result["bands"]

    if len(bands_micro) == 0 or len(bands_mems) == 0:
        return {
            "bands": np.array([]),
            "levels_micro": np.array([]),
            "levels_mems": np.array([]),
            "spl_micro": np.array([]),
            "spl_mems": np.array([]),
            "diff_db": np.array([])
        }

    if bands_micro.shape != bands_mems.shape or not np.allclose(
        bands_micro, bands_mems, rtol=1e-8, atol=1e-10
    ):
        raise ValueError("Les bandes micro et MEMS ne coïncident pas.")

    levels_micro = micro_result["levels"]
    levels_mems = mems_result["levels"]

    spl_micro = 20 * np.log10(np.maximum(levels_micro, 1e-30) / 2e-5)
    spl_mems = 20 * np.log10(np.maximum(levels_mems, 1e-30) / 2e-5)
    diff_db = spl_mems - spl_micro

    return {
        "bands": bands_micro,
        "levels_micro": levels_micro,
        "levels_mems": levels_mems,
        "spl_micro": spl_micro,
        "spl_mems": spl_mems,
        "diff_db": diff_db
    }


def summarize_calibration_results(df_long):
    """
    Agrège les résultats de calibration par bande.
    """
    if df_long.empty:
        return pd.DataFrame(columns=[
            "band_center_Hz", "n", "mean_diff_db", "std_diff_db", "ic95_db", "ip95_db"
        ])

    grouped = df_long.groupby("band_center_Hz")["diff_db"]

    summary = grouped.agg(["count", "mean", "std"]).reset_index()
    summary.rename(columns={
        "count": "n",
        "mean": "mean_diff_db",
        "std": "std_diff_db"
    }, inplace=True)

    ic95_list = []
    ip95_list = []

    for _, row in summary.iterrows():
        n = int(row["n"])
        s = row["std_diff_db"]

        if not np.isfinite(s):
            s = 0.0

        if n > 1:
            tval = stats.t.ppf(0.975, df=n - 1)
            ic95 = tval * s / np.sqrt(n)
            ip95 = tval * s * np.sqrt(1 + 1 / n)
        else:
            ic95 = 0.0
            ip95 = 0.0

        ic95_list.append(ic95)
        ip95_list.append(ip95)

    summary["ic95_db"] = ic95_list
    summary["ip95_db"] = ip95_list

    return summary


def run_calibration(config, correspondance_table, read_info, visu, window_type="hann", plot_results=True):
    """
    Lance la calibration complète sur tous les fichiers.
    """
    print(f"Dossier calibration : {config.validation_folder}")
    print(f"Dossier sortie      : {config.out_folder}")
    print(f"Base name           : {config.base_name}")

    all_df = []

    for file_number, corr_map in correspondance_table.items():
        visu.print_section(f"Traitement fichier {file_number}")

        file_dat = read_info.find_auto_file(
            config.validation_folder,
            config.base_name,
            file_number,
            "dat"
        )

        file_ldsf = read_info.find_auto_file(
            config.validation_folder,
            config.base_name,
            file_number,
            "ldsf"
        )

        print(f"DAT  : {file_dat.name}")
        print(f"LDSF : {file_ldsf.name}")

        Sigs_val, config = read_info.load_validation_data(
            config,
            file_dat=file_dat
        )

        micro_channels = list(corr_map.keys())
        micros_dict = read_info.load_reference_microphones(
            file_ldsf,
            micro_channels
        )

        pair_results, df_long = process_calibration_file(
            Sigs_val=Sigs_val,
            micros_dict=micros_dict,
            corr_map=corr_map,
            config=config,
            file_number=file_number,
            window_type=window_type
        )

        csv_path = config.out_folder / f"{config.base_name}{file_number}_bands_pa.csv"
        df_long.to_csv(csv_path, index=False)
        print(f"✅ Sauvegardé : {csv_path}")

        all_df.append(df_long)

        if plot_results:
            for pair_result in pair_results:
                plot_calibration_pair(pair_result)

    visu.print_section("Agrégation finale")

    if len(all_df) == 0:
        raise RuntimeError("Aucun résultat de calibration disponible.")

    df_all = pd.concat(all_df, ignore_index=True)

    all_csv_path = config.out_folder / f"{config.base_name}_all_pairs.csv"
    df_all.to_csv(all_csv_path, index=False)
    print(f"✅ Sauvegardé : {all_csv_path}")

    summary_df = summarize_calibration_results(df_all)

    summary_csv_path = config.out_folder / f"{config.base_name}_summary.csv"
    summary_df.to_csv(summary_csv_path, index=False)
    print(f"✅ Sauvegardé : {summary_csv_path}")

    txt_path = config.out_folder / f"{config.base_name}_mean_diff_per_band.txt"
    summary_df[["band_center_Hz", "mean_diff_db"]].to_csv(
        txt_path,
        sep=" ",
        index=False,
        header=["band_center_Hz", "mean_diff_db"]
    )
    print(f"✅ Fichier correction sauvegardé : {txt_path}")

    print("\n[OK] Calibration terminée avec succès.")
    return df_all, summary_df