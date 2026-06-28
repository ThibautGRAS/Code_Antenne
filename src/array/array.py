# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 15:30:50 2026

@author: gras
"""

import os

import numpy as np

# Backend interactif par defaut (sans ecraser un choix amont, ex. live -> Agg).
os.environ.setdefault("MPLBACKEND", "Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

from matplotlib.cm import ScalarMappable

from src.visu import (
    get_cube_bounds,
    plot_cube_edges,
    add_view_buttons,
    plot_sphere
)

# ============================================================================
# ARRAY - Fonction liees a la geometrie de l antenne
# ============================================================================


def compute_array_directivity_3d_fast(
    mic_positions,
    fmin,
    fmax,
    Nf=50,
    c=340,
    resolution=2
):    

    mic_positions = np.asarray(mic_positions)
    N = mic_positions.shape[0]

    r_mic = mic_positions - np.mean(mic_positions, axis=0)

    freqs = np.linspace(fmin, fmax, Nf)

    theta = np.radians(np.arange(0, 180 + resolution, resolution))
    phi   = np.radians(np.arange(0, 360 + resolution, resolution))
    TH, PH = np.meshgrid(theta, phi)

    U = np.stack([
        np.sin(TH) * np.cos(PH),
        np.sin(TH) * np.sin(PH),
        np.cos(TH)
    ], axis=-1)

    Ur = np.tensordot(U, r_mic, axes=([2],[1]))

    AF_all = np.zeros((Nf, *TH.shape), dtype=float)
    AF_max_per_freq = np.zeros(Nf, dtype=float)

    for i_f, f in enumerate(freqs):
        k = 2 * np.pi * f / c
        AF = np.sum(np.exp(-1j * k * Ur), axis=2)
        AF_abs = np.abs(AF)
        AF_all[i_f] = AF_abs
        AF_max_per_freq[i_f] = AF_abs.max()

    # Normalisation globale
    AF_norm_global = AF_all / AF_all.max()
    # Normalisation par fréquence
    AF_norm_per_freq = AF_all / AF_max_per_freq[:, np.newaxis, np.newaxis]

    return AF_norm_global, AF_norm_per_freq, freqs, theta, phi, r_mic, AF_max_per_freq 
    
    
def plot_directivity_3d_at_frequency(
    AF_norm_all,
    freqs,
    theta,
    phi,
    r_mic,
    f_plot,
    scale='dB',
    dB_floor=-40,
    show_mics=True
):
    """
    Trace la directivité 3D pour une fréquence donnée,
    à partir d'une normalisation globale.
    """

    # --- Sélection fréquence ---
    idx = np.argmin(np.abs(freqs - f_plot))
    f_sel = freqs[idx]
    AF = AF_norm_all[idx]

    # --- Échelle ---
    if scale.lower() == 'db':
        AF_plot = 20 * np.log10(AF + 1e-12)
        AF_plot = np.clip(AF_plot, dB_floor, 0)
        clim = (dB_floor, 0)
        title_scale = '[dB]'
    else:
        AF_plot = AF
        clim = (0, 1)
        title_scale = '[lin]'

    # --- Coordonnées sphériques ---
    TH, PH = np.meshgrid(theta, phi)
    R = AF

    X = R * np.sin(TH) * np.cos(PH)
    Y = R * np.sin(TH) * np.sin(PH)
    Z = R * np.cos(TH)

    # --- Figure ---
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    norm_colors = (AF_plot - clim[0]) / (clim[1] - clim[0] + 1e-12)

    ax.plot_surface(
        X, Y, Z,
        facecolors=plt.cm.viridis(norm_colors),
        rstride=1, cstride=1,
        antialiased=True, alpha=0.85
    )

    # --- Colorbar ---
    mappable = ScalarMappable(cmap=plt.cm.viridis)
    mappable.set_array(AF_plot)
    mappable.set_clim(*clim)
    fig.colorbar(mappable, ax=ax, shrink=0.6, aspect=10)

    # --- Micros ---
    if show_mics:
        ax.scatter(
            r_mic[:, 0], r_mic[:, 1], r_mic[:, 2],
            c='r', s=25, alpha=0.3
        )

    # --- Boutons de vue (fonction déjà dans ton fichier) ---
    add_view_buttons(fig, ax)