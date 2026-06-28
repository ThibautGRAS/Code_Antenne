# -*- coding: utf-8 -*-
"""
Created on Wed Nov 26 10:50:07 2025

@author: gras
"""

import numpy as np
import pandas as pd 
import matplotlib
matplotlib.use('Qt5Agg')


from scipy.signal import spectrogram, windows

from pathlib import Path

from src.read_info import load_band_corrections

# ============================================================================
# UTILITAIRES CALCUL SIGNAL

def calc_corr(fs, df=1, window_type='hann'):
    """
    Calcule le facteur de correction d'une fenêtre pour un spectre FFT.

    Parametres :
    -----------
    fs : float
        Fréquence d'échantillonnage (Hz).
    df : float, optionnel
        Résolution fréquentielle souhaitée (Hz). Par défaut = 1 Hz.
    window_type : str, optionnel
        Type de fenêtre à utiliser. Par défaut 'hann' (Hanning).

    Retour :
    -------
    corr : float
        Facteur de correction pour compenser l'effet de la fenêtre sur le RMS.
        Utilisé pour normaliser l'énergie du spectre.
    """

    # Calcul du nombre de points nécessaires pour atteindre la résolution df
    nperseg = int(fs / df)

    # Création de la fenêtre
    if window_type.lower() == 'hann':
        w = windows.hann(nperseg)
    elif window_type.lower() == 'hamming':
        w = windows.hamming(nperseg)
    elif window_type.lower() == 'blackman':
        w = windows.blackman(nperseg)
    else:
        raise ValueError(f"Fenêtre '{window_type}' non supportée")

    # Calcul du facteur de correction :
    # Corrige l'amplitude du spectre pour compenser la perte d'énergie due à la fenêtre
    # Formule : N * sum(w^2) / (sum(w)^2)
    corr = (len(w) * np.sum(w ** 2)) / (np.sum(w) ** 2)

    return corr

def MIScalc(data, config, batch_size=32, verbose= True):
    """
    Version optimisée : spectrogramme par batch de capteurs + calcul CSM.
    Sélection de fréquence flexible :
      - fmin_bf=None et/ou fmax_bf=None => pas de borne de ce côté.
      - les deux None => toutes les fréquences.
    """

    # --- Paramètres issus du config ---
    delta_f   = config.delta_f
    fs        = config.Fe
    diagremov = config.diag_remove

    # Recouvrement des trames du spectrogramme, en fraction de la fenetre.
    # 0.5 = 50 % (defaut historique). Borne a [0, 0.95].
    overlap = float(getattr(config, "overlap", 0.5))
    overlap = min(max(overlap, 0.0), 0.95)

    # f_min / f_max peuvent être absents ou None
    f_min = getattr(config, "fmin_bf", None)
    f_max = getattr(config, "fmax_bf", None)

    M, N = data.shape

    lenframe = int(fs / delta_f)
    if lenframe > N:
        data = np.pad(data, ((0, 0), (0, lenframe - N)), constant_values=0)
        N = data.shape[1]

    # scipy exige noverlap < nperseg
    noverlap = min(int(round(overlap * lenframe)), lenframe - 1)

    Sxx_list = []
    f = None

    # --- Traitement par batch ---
    for start in range(0, M, batch_size):
        end = min(start + batch_size, M)

        if verbose:
            print(f"Calcul spectrogramme batch {start}:{end} / {M}")

        batch = data[start:end]

        f, t, Sxx_batch = spectrogram(
            batch,
            fs=fs,
            window='hann',
            nperseg=lenframe,
            noverlap=noverlap,
            scaling='spectrum',
            mode='complex'
        )

        Sxx_list.append(Sxx_batch.astype(np.complex64))

    # Reconstruction (M, n_freqs, n_frames)
    Sxx = np.concatenate(Sxx_list, axis=0)

    # --- Sélection des fréquences (gère les None) ---
    if f_min is None and f_max is None:
        freq_mask = slice(None)         # toutes fréquences
    elif f_min is None:
        freq_mask = (f <= f_max)        # uniquement borne haute
    elif f_max is None:
        freq_mask = (f >= f_min)        # uniquement borne basse
    else:
        freq_mask = (f >= f_min) & (f <= f_max)

    # Sécurité : si masque booléen vide
    if not isinstance(freq_mask, slice) and not np.any(freq_mask):
        raise ValueError(f"Aucune fréquence dans la sélection : f_min={f_min}, f_max={f_max}")

    f_selected = f[freq_mask] if not isinstance(freq_mask, slice) else f
    Sxx_band   = Sxx[:, freq_mask, :]   # (M, n_sel, n_frames)
    nframes    = Sxx_band.shape[2]

    # --- Calcul des CSM sur les fréquences sélectionnées ---
    list_CSM = []
    for i in range(Sxx_band.shape[1]):
        Xf = Sxx_band[:, i, :]                 # (M, nframes)
        CSM_f = (Xf @ Xf.conj().T) / nframes   # (M, M)
        if diagremov:
            np.fill_diagonal(CSM_f, 0)
        list_CSM.append(CSM_f.astype(np.complex64))

    return f_selected, list_CSM


def select_CSM(f, CSM, f_min, f_max, verbose=True):
    """
    Retourne (f_selected, list_CSM) prêts pour compute_beamforming().
    - f_selected : ndarray (n_sel,)
    - list_CSM   : liste de (M,M) complex

    CSM peut être :
      - un ndarray (n_freqs, M, M)
      - ou déjà une liste de matrices (M,M)
    """
    f = np.asarray(f)
    mask = (f >= f_min) & (f <= f_max)

    if not np.any(mask):
        raise ValueError(f"Aucune fréquence dans [{f_min}, {f_max}] Hz.")

    f_selected = f[mask]

    # Toujours renvoyer une LISTE de matrices
    if isinstance(CSM, list):
        list_CSM = [c for c, m in zip(CSM, mask) if m]
    else:
        CSM = np.asarray(CSM)
        list_CSM = list(CSM[mask])   # CSM[mask] -> (n_sel, M, M), puis converti en liste

    if verbose:
        print(f"Fréquences sélectionnées: {len(f_selected)}  ({f_selected[0]:.2f} -> {f_selected[-1]:.2f} Hz)")

    return f_selected, list_CSM



def bands_levels_tiers_oct_math(frq, Sxx, f_min, f_max, Corr=1.0, PSD=False):
    """
    Calcule les niveaux RMS par bande tiers d'octave.

    Parameters:
    -----------
    frq : array_like
        Fréquences du spectre.
    Sxx : array_like
        Spectre linéaire ou PSD (Pa²/Hz si PSD=True).
    f_min : float
        Fréquence centrale minimale.
    f_max : float
        Fréquence centrale maximale.
    PSD : bool
        True si Sxx est un PSD. False si spectre linéaire.
    Corr : float
        Facteur de correction pour spectre linéaire (ignoré si PSD=True).

    Returns:
    --------
    bands : np.ndarray
        Fréquences centrales des bandes (Hz).
    levels : np.ndarray
        Niveaux RMS par bande (Pa).
    """

    bands, levels = [], []
    df = frq[1] - frq[0]          # Résolution fréquentielle
    f_center = f_min

    while f_center * 2**(1/6) < f_max:
        # Bornes de la bande 1/3 d'octave
        f_inf = f_center / 2**(1/6)
        f_sup = f_center * 2**(1/6)

        # Indices des fréquences les plus proches
        indmin = np.argmin(np.abs(frq - f_inf))
        indmax = np.argmin(np.abs(frq - f_sup))

        if indmax > indmin:
            band = Sxx[indmin:indmax+1]

            # Calcul RMS selon type de spectre
            if PSD:
                rms = np.sqrt(df * (band[0]/2 + np.sum(band[1:-1]) + band[-1]/2))
            else:
                rms = np.sqrt((band[0]/2 + np.sum(band[1:-1]) + band[-1]/2) / Corr)

            bands.append(f_center)
            levels.append(rms)

        # Bande suivante (1/3 d'octave)
        f_center *= 2**(1/3)

    return np.array(bands), np.array(levels)

def bands_levels_tiers_oct(frq, Sxx, f_min, f_max, Corr=1.0, PSD=False):

    # bandes normalisées IEC
    bands_std = np.array([
        16, 20, 25, 31.5, 40, 50,
        63, 80, 100, 125, 160, 200,
        250, 315, 400, 500, 630, 800,
        1000, 1250, 1600, 2000, 2500, 3150,
        4000, 5000, 6300, 8000, 10000, 12500,
        16000, 20000
    ])

    # sélection de la plage utile
    bands = bands_std[(bands_std >= f_min) & (bands_std <= f_max)]

    levels = []
    df = frq[1] - frq[0]

    for f_center in bands:

        f_inf = f_center / 2**(1/6)
        f_sup = f_center * 2**(1/6)

        indmin = np.argmin(np.abs(frq - f_inf))
        indmax = np.argmin(np.abs(frq - f_sup))

        if indmax > indmin:
            band = Sxx[indmin:indmax+1]

            if PSD:
                rms = np.sqrt(df * (band[0]/2 + np.sum(band[1:-1]) + band[-1]/2))
            else:
                rms = np.sqrt((band[0]/2 + np.sum(band[1:-1]) + band[-1]/2) / Corr)

            levels.append(rms)
        else:
            levels.append(np.nan)

    return bands, np.array(levels)


def compute_all_mems_spectra(Sigs_val, geo_positions, config, window_type='hann', corr=True):
    """
    Version spécialisée pour les MEMS du cube avec géométrie.
    """
    chan_to_pos = {i + 1: tuple(p) for i, p in enumerate(geo_positions)} 
    
    # On conserve les voies en dehors compteur et jusqu'au dernier micro renseigné en position
    signals = Sigs_val[config.Nbcompteur:len(geo_positions)+1, :]
    
    if corr:
        bands_corr, diff_corr = load_band_corrections(config)
    else:
        bands_corr, diff_corr = None, None

    all_results = compute_all_channels_spectra(
        signals=signals,
        fs=config.Fe,
        df_band=config.df_band,
        tmin=config.tmin,
        tmax=config.tmax,
        window_type=window_type,
        input_in_pa=False,
        smems=config.SMEMS,
        apply_band_correction=corr,
        bands_corr=bands_corr,
        diff_corr=diff_corr,
        channel_ids=list(range(1, len(geo_positions)+1)),
        fmin=1.0,
        fmax=config.Fe/2
    )

    # Gestion éventuelle des voies manquantes
    for ch in range(1, len(geo_positions)+1):
        if ch not in all_results:
            all_results[ch] = {k: np.array([]) for k in ('freq','Sxx','bands','levels','Sxx_corr','levels_corr')}

    return all_results, chan_to_pos

def compute_all_channels_spectra(
    signals,
    fs,
    df_band,
    tmin=0.0,
    tmax=None,
    window_type='hann',
    input_in_pa=True,
    smems=None,
    apply_band_correction=False,
    bands_corr=None,
    diff_corr=None,
    channel_ids=None,
    fmin=1.0,
    fmax=None
):
    """
    Calcule les spectres et niveaux tiers d'octave pour un ensemble de voies.

    Parameters
    ----------
    signals : np.ndarray
        Tableau shape (n_channels, n_samples).
    fs : float
        Fréquence d'échantillonnage.
    df_band : float
        Résolution fréquentielle Welch.
    tmin, tmax : float
        Fenêtre temporelle analysée.
    window_type : str
        Fenêtre Welch.
    input_in_pa : bool
        True si les signaux sont déjà en Pa.
        False si les signaux sont en counts et doivent être divisés par smems.
    smems : float | None
        Facteur de conversion counts -> Pa si input_in_pa=False.
    apply_band_correction : bool
        Applique une correction fréquentielle si True.
    bands_corr, diff_corr : np.ndarray | None
        Correction moyenne par bande.
    channel_ids : list | None
        Identifiants des voies. Si None -> [1..n_channels]
    fmin, fmax : float | None
        Bornes pour les bandes tiers d'octave.

    Returns
    -------
    all_results : dict
        all_results[ch] = {...}
    """
    import numpy as np
    from scipy.signal import welch
    from scipy.interpolate import interp1d

    n_channels, n_samples = signals.shape

    if tmax is None:
        tmax = n_samples / fs
    if fmax is None:
        fmax = fs / 2
    if channel_ids is None:
        channel_ids = list(range(1, n_channels + 1))

    t = np.arange(n_samples) / fs
    j1 = np.argmin(np.abs(t - tmin))
    j2 = np.argmin(np.abs(t - tmax))

    corr_factor = calc_corr(fs, df=df_band, window_type=window_type)

    corr_interp = None
    if apply_band_correction:
        if bands_corr is None or diff_corr is None:
            raise ValueError("bands_corr et diff_corr doivent être fournis si apply_band_correction=True")
        corr_interp = interp1d(
            bands_corr, diff_corr,
            kind='linear',
            bounds_error=False,
            fill_value=0.0
        )

    all_results = {}

    for i, ch in enumerate(channel_ids):
        sig = signals[i, j1:j2]

        if not input_in_pa:
            if smems is None:
                raise ValueError("smems doit être fourni si input_in_pa=False")
            sig = sig / smems

        frq, Sxx = welch(
            sig,
            fs=fs,
            window=window_type,
            nperseg=int(fs / df_band),
            noverlap=int(fs / (2 * df_band)),
            scaling='spectrum'
        )

        bands, levels = bands_levels_tiers_oct(
            frq, Sxx, fmin, fmax, Corr=corr_factor
        )

        result = dict(
            freq=frq,
            Sxx=Sxx,
            bands=bands,
            levels=levels
        )

        if apply_band_correction:
            corr_vals_bands = corr_interp(bands)
            levels_corr = levels * 10**(-corr_vals_bands / 20)

            corr_vals_Sxx = corr_interp(frq)
            Sxx_corr = Sxx * 10**(-corr_vals_Sxx / 10)

            result["Sxx_corr"] = Sxx_corr
            result["levels_corr"] = levels_corr

        all_results[ch] = result

    duree = (j2 - j1) / fs
    print("\n[OK] Calcul des spectres terminé.")
    print("Paramètres :")
    print(f"  • Fe = {fs} Hz")
    print(f"  • Fenêtre Welch = {window_type}")
    print(f"  • Δf = {df_band} Hz")
    print(f"  • Durée analysée = {duree:.3f} s")

    return all_results

def extract_chosen_band_levels(all_results, config):
    """
    Extrait le niveau en dB SPL à la bande choisie pour chaque MEMS,
    sans appliquer la correction MEMS.
    """
    db_vals = {}

    for ch, d in all_results.items():
        bands, levels = d['bands'], d['levels']

        # MEMS vide
        if len(bands) == 0:
            db_vals[ch] = np.nan
            continue

        # Conversion Pa RMS → dB SPL
        mems_db = 20 * np.log10(levels / 2e-5)

        # Bande hors domaine
        if not (bands[0] <= config.chosen_band <= bands[-1]):
            db_vals[ch] = np.nan
            continue

        # Interpolation linéaire pour obtenir la valeur à la bande choisie
        db_vals[ch] = float(np.interp(config.chosen_band, bands, mems_db))
        
    print(f"\n [OK] Niveau extrait a la bande {config.chosen_band} Hz (en dB SPL) pour tous les MEMS.")

    return db_vals

def select_mics_every_n(chan_to_pos, n):
    """
    Sélectionne un micro sur n dans le dictionnaire chan_to_pos.
    Retourne un sous-dictionnaire avec les clés sélectionnées.
    """
    keys_sorted = sorted(chan_to_pos.keys())
    selected_keys = keys_sorted[::n]
    print(f"\n [OK] {len(selected_keys)} micros selectiones (1 sur {n}) parmi {len(keys_sorted)} disponibles.")
    return {k: chan_to_pos[k] for k in selected_keys}

def extract_mic_signals(Sigs_val, config):
    """
    Extrait les signaux MEMS (en Pa) et les positions géométriques.
    """
    if getattr(config, "geo_file", None) and Path(config.geo_file).is_file():
        geo_df = pd.read_csv(config.geo_file, sep=';')
        n_mems = len(geo_df)
        data = Sigs_val[config.Nbcompteur:config.Nbcompteur + n_mems, :] / config.SMEMS
    else:
        data = Sigs_val / config.SMEMS

    return data

def db_to_pa(db_values):
    return 20e-6 * 10**(np.array(db_values)/20.0)

def pa_to_db(pa_values):
    return 20.0 * np.log10(np.array(pa_values)/20e-6)