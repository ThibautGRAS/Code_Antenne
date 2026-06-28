# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 14:19:23 2026

@author: gras
"""

import numpy as np
import pandas as pd


from src.visu import (
    get_cube_bounds,
    plot_cube_edges,
    add_view_buttons,
    plot_sphere
)

from .beamforming_mesh import load_mesh, transform_mesh
from .beamforming_visu import compute_mesh_visibility
from .beamforming_signal import MUSIC_cart, Bartlett_cart, OBF_cart

from src.signal_process import MIScalc

def run_beamforming_pipeline(f_selected, list_CSM, geo_positions, config):
    """
    Pipeline beamforming :
    - lecture mesh
    - transformation mesh
    - visibilité
    - beamforming
    - conversion SPL
    """

    # 1) Lecture mesh
    points_stl = load_mesh(config.file_mesh, factor_dim=1)

    # 2) Transformation mesh
    points, grid_points = transform_mesh(
        points_stl,
        config.rotation_deg,
        config.offsetx,
        config.offsety,
        config.offsetz
    )

    # 3) Visibilité
    visibility_mask = compute_mesh_visibility(
        grid_points,
        geo_positions,
        config.max_angle_deg,
        config.plot_visibility
    ) if config.max_angle_deg is not None else None

    # 4) Beamforming
    WBF_map = compute_beamforming(
        f_selected,
        list_CSM,
        grid_points,
        geo_positions,
        config.method.lower(),
        config.n_sources,
        config.z,
        config.R,
        visibility_mask,
        config.nmodei
    )

    # 5) Conversion SPL
    eps = 1e-12
    if config.method.lower() in ['bartlett', 'obf']:
        SPL_values = 10 * np.log10(np.abs(WBF_map + eps) / (2e-5)**2)
    else:
        SPL_values = 10 * np.log10(
            np.real(WBF_map) / np.max(np.real(WBF_map)) + eps
        )

    return SPL_values, points, grid_points

def run_beamforming_pipeline0(Sigs_val, geo_positions, config):
    """
    Pipeline principal de beamforming :
    - extraction signaux
    - lecture mesh
    - transformation mesh
    - visibilité
    - calcul CSM
    - beamforming
    """

    # 1) Extraction signaux MEMS
    data = Sigs_val[1:len(geo_positions)+1, :] / config.SMEMS

    # 2) Lecture mesh
    points_stl = load_mesh(config.file_mesh, factor_dim=1)
    
    # 3) Transformation mesh
    points, grid_points = transform_mesh(
        points_stl,
        config.rotation_deg,
        config.offsetx,
        config.offsety,
        config.offsetz
    )

    # 4) Visibilité
    visibility_mask = compute_mesh_visibility(
        grid_points,
        geo_positions,
        config.max_angle_deg,
        config.plot_visibility
    ) if config.max_angle_deg is not None else None

    # 5) CSM bande fine
    f_selected, list_CSM = MIScalc(
        data,
        config.fmin_bf,
        config.fmax_bf,
        config.delta_f,
        config.Fe,
        diagremov=config.diag_remove
    )

    # 6) Beamforming
    WBF_map = compute_beamforming(
        f_selected,
        list_CSM,
        grid_points,
        geo_positions,
        config.method.lower(),
        config.n_sources,
        config.z,
        config.R,
        visibility_mask,
        config.nmodei
    )

    # 7) Conversion SPL
    eps = 1e-12
    if config.method.lower() in ['bartlett', 'obf']:
        SPL_values = 10 * np.log10(np.abs(WBF_map + eps) / (2e-5)**2)
    else:
        SPL_values = 10 * np.log10(
            np.real(WBF_map) / np.max(np.real(WBF_map)) + eps
        )

    return SPL_values, points, grid_points, list_CSM[-1]


def compute_beamforming(f_selected, list_CSM, grid_points, geo_positions,
                        method, n_sources, z, R, visibility_mask, nmodei):
    """
    Calcule la carte de beamforming en sommant les contributions
    de chaque fréquence sélectionnée.

    Paramètres :
        f_selected     : fréquences sélectionnées (array)
        list_CSM       : liste des matrices interspectrales
        grid_points    : points du mesh transformé
        geo_positions  : positions des micros
        method         : 'bartlett', 'music', 'obf'
        n_sources      : nb sources MUSIC
        z              : plan réfléchissant
        R              : coefficient de réflexion
        visibility_mask: masque de visibilité (ou None)
        nmodei         : mode OBF sélectionné (ou None)

    Retour :
        WBF_map : carte BF sommée sur toutes les fréquences
    """

    WBF_map = np.zeros(grid_points.shape[0], dtype=float)

    print("\n=== Début du calcul Beamforming ===")
    print(f"Nombre de fréquences : {len(f_selected)}\n")

    # Boucle sur les fréquences
    for idx, (f, MISin) in enumerate(zip(f_selected, list_CSM), start=1):

        # 🔍 Affichage progression
        print(f"[{idx}/{len(f_selected)}] Traitement fréquence : {f:.2f} Hz")

        # --- Sélection de la méthode ---
        if method == 'bartlett':
            BF_f = Bartlett_cart(
                f, MISin, grid_points, geo_positions,
                visibility_mask=visibility_mask, z_plane=z, R=R
            )

        elif method == 'music':
            BF_f = MUSIC_cart(
                f, MISin, grid_points, geo_positions,
                n_sources=n_sources, z_plane=z, R=R
            )

        elif method == 'obf':
            Bfall, BF_modes = OBF_cart(
                f, MISin, grid_points, geo_positions,
                n_modes=n_sources, z_plane=z, R=R
            )
            BF_f = Bfall if nmodei is None else BF_modes[nmodei, :]

        else:
            raise ValueError(f"Méthode BF non supportée : {method}")

        # Accumulation
        WBF_map += BF_f

    print("\n=== Beamforming terminé ===\n")

    return WBF_map


