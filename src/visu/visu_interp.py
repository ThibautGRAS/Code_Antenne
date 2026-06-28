# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 15:02:04 2026

@author: gras
"""

import os

import numpy as np

# Backend interactif par defaut (sans ecraser un choix amont, ex. live -> Agg).
os.environ.setdefault("MPLBACKEND", "Qt5Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


from src.signal_process import db_to_pa
from src.signal_process import pa_to_db

from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree
from scipy.ndimage import gaussian_filter

from src.visu import (get_cube_bounds,plot_cube_edges,
                  add_view_buttons, plot_sphere, prepare_plot_data, plot_micro_spheres
) 

  

# ============================================================================
# VISUALISATION - Interpolation de faces d'un cube
# ============================================================================

def plot_surfaces(
    ax, mode, db_vals, chan_to_pos, geo_positions,
    config, norm, alphaa, method, interp_space
):   
    
    """
    Affiche les surfaces colorées du cube selon le mode choisi.

    Paramètres
    ----------
    ax : Axes3D
        Axes matplotlib 3D.
    mode : str
        'mesh' ou 'smooth'.
    db_vals : dict
        Niveau SPL par MEMS.
    chan_to_pos : dict
        Position des MEMS.
    geo_positions : ndarray
        Positions (N x 3).
    config : Config
        Paramètres globaux.
    norm : Normalize
        Normalisation des couleurs.
    alphaa : float
        Transparence des surfaces.
    method : str
        Méthode RBF.
    interp_space : str
        'log' ou 'linear'.

    Retour
    ------
    title : str
        Titre à afficher sur la figure.
    """

    bounds = get_cube_bounds(geo_positions)
    cmap = plt.cm.jet

    # -------------------------
    # MODE 1 : MESH (IDW face par face)
    # -------------------------
    if mode == 'mesh':
        all_patches = []

        # Liste des 6 faces du cube
        face_list = [
            ('x', bounds[0][0], bounds[1:]),  # face x_min
            ('x', bounds[0][1], bounds[1:]),  # face x_max
            ('y', bounds[1][0], (bounds[0], bounds[2])),
            ('y', bounds[1][1], (bounds[0], bounds[2])),
            ('z', bounds[2][0], bounds[0:2]),
            ('z', bounds[2][1], bounds[0:2])
        ]

        # Génération des patchs pour chaque face
        for face_type, coord_fixed, f_bounds in face_list:
            patches = create_face_mesh_idw(
                face_type,
                coord_fixed,
                f_bounds,
                db_vals,
                chan_to_pos,
                config.mesh_size,
                config.max_distance
            )
            all_patches.extend(patches)

        # Affichage des patchs
        for vertices, value in all_patches:
            color = cmap(norm(value))
            poly = Poly3DCollection(
                [vertices],
                facecolors=color,
                linewidths=0.2,
                edgecolors='gray',
                alpha=alphaa
            )
            ax.add_collection3d(poly)

        title = f"Champ Acoustique - Mode Mesh\nBande {config.chosen_band:.0f} Hz"

    # -------------------------
    # MODE 2 : SMOOTH (RBF globale)
    # -------------------------
    else:
        faces_data = create_3d_global_interpolation(
            db_vals,
            chan_to_pos,
            bounds,
            config.smooth_resolution,
            freq=config.chosen_band,
            interp_space=interp_space,
            method=method
        )

        # Affichage des surfaces interpolées
        for face in faces_data:
            if face is not None:
                X, Y, Z, values = face
                ax.plot_surface(
                    X, Y, Z,
                    facecolors=cmap(norm(values)),
                    alpha=alphaa,
                    linewidth=0,
                    antialiased=True,
                    shade=False
                )

        title = (
            f"Champ Acoustique - RBF ({method})\n"
            f"Bande {config.chosen_band:.0f} Hz | "
            f"Résolution {config.smooth_resolution}x{config.smooth_resolution}"
        )

    return title

def create_face_mesh_idw(
    face_type,
    coord_fixed,
    bounds,
    db_vals,
    chan_to_pos,
    mesh_size,
    max_distance,
    interpolate_in_pa=True,
    power=1.0,
    eps=1e-12
):
    (min1, max1), (min2, max2) = bounds
    n_cells_1 = int(np.ceil((max1 - min1) / mesh_size))
    n_cells_2 = int(np.ceil((max2 - min2) / mesh_size))

    patches = []
    grid1 = np.linspace(min1, max1, n_cells_1 + 1)
    grid2 = np.linspace(min2, max2, n_cells_2 + 1)

    for i in range(len(grid1) - 1):
        for j in range(len(grid2) - 1):
            c1_center = 0.5 * (grid1[i] + grid1[i + 1])
            c2_center = 0.5 * (grid2[j] + grid2[j + 1])

            if face_type == 'x':
                xc, yc, zc = coord_fixed, c1_center, c2_center
            elif face_type == 'y':
                xc, yc, zc = c1_center, coord_fixed, c2_center
            else:
                xc, yc, zc = c1_center, c2_center, coord_fixed

            values_list = []
            weights_list = []

            for ch, pos in chan_to_pos.items():
                xm, ym, zm = pos
                d3 = np.sqrt((xm - xc)**2 + (ym - yc)**2 + (zm - zc)**2)

                if d3 <= max_distance:
                    val = db_to_pa(db_vals[ch]) if interpolate_in_pa else db_vals[ch]
                    w = 1.0 / max(d3, eps)**power
                    values_list.append(val)
                    weights_list.append(w)

            if len(values_list) == 0:
                continue

            values_arr = np.array(values_list, dtype=float)
            weights_arr = np.array(weights_list, dtype=float)

            weighted_mean = np.sum(weights_arr * values_arr) / np.sum(weights_arr)

            value_db = pa_to_db(weighted_mean) if interpolate_in_pa else weighted_mean

            if face_type == 'x':
                vertices = [
                    [coord_fixed, grid1[i],   grid2[j]],
                    [coord_fixed, grid1[i+1], grid2[j]],
                    [coord_fixed, grid1[i+1], grid2[j+1]],
                    [coord_fixed, grid1[i],   grid2[j+1]]
                ]
            elif face_type == 'y':
                vertices = [
                    [grid1[i],   coord_fixed, grid2[j]],
                    [grid1[i+1], coord_fixed, grid2[j]],
                    [grid1[i+1], coord_fixed, grid2[j+1]],
                    [grid1[i],   coord_fixed, grid2[j+1]]
                ]
            else:
                vertices = [
                    [grid1[i],   grid2[j],   coord_fixed],
                    [grid1[i+1], grid2[j],   coord_fixed],
                    [grid1[i+1], grid2[j+1], coord_fixed],
                    [grid1[i],   grid2[j+1], coord_fixed]
                ]

            patches.append((vertices, value_db))

    return patches


def compute_mean_spacing(chan_to_pos, bounds):
    """
    Calcule l'espacement moyen inter-micros sur chaque face
    et retourne la moyenne globale.
    
    Utilisé pour fixer epsilon de la RBF gaussienne.
    """
    from scipy.spatial.distance import cdist
    
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    tol = 0.05   # tolérance appartenance à une face [m]
    
    positions = np.array(list(chan_to_pos.values()))
    
    face_specs = [
        (positions[:, 0], x_min, 0),   # face x_min → coords y,z
        (positions[:, 0], x_max, 0),
        (positions[:, 1], y_min, 1),   # face y_min → coords x,z
        (positions[:, 1], y_max, 1),
        (positions[:, 2], z_min, 2),   # face z_min → coords x,y
        (positions[:, 2], z_max, 2),
    ]
    
    spacings = []
    
    for coord_vals, coord_fixed, axis_idx in face_specs:
        mask = np.abs(coord_vals - coord_fixed) < tol
        mics_face = positions[mask]
        
        if len(mics_face) < 2:
            continue
        
        # Indices des 2 axes libres selon la face
        free_axes = [i for i in range(3) if i != axis_idx]
        mics_2d   = mics_face[:, free_axes]
        
        # Distance au plus proche voisin pour chaque micro
        D = cdist(mics_2d, mics_2d)
        np.fill_diagonal(D, np.inf)
        nn_dists = np.min(D, axis=1)
        
        spacing_face = np.mean(nn_dists)
        spacings.append(spacing_face)
        print(f"  Face axis={axis_idx} val={coord_fixed:.2f} : "
              f"{mask.sum()} micros  espacement={spacing_face:.3f} m")
    
    spacing_mean = np.mean(spacings) if spacings else 0.15
    print(f"  Espacement moyen global : {spacing_mean:.3f} m")
    
    return spacing_mean

def create_3d_global_interpolation(db_vals, chan_to_pos, bounds, 
                                   resolution=100, freq=1000,
                                   interp_space='log',
                                   method='thin_plate',
                                   smoothing=0.01,
                                   max_distance=None):
    """
    Interpolation RBF 3D continue sur tout le volume, puis extraction des faces.
    Garantit la continuité inter-faces.
    """

    # 1. Préparation des données
    coords = []
    vals = []
    for ch, pos in chan_to_pos.items():
        db_val = db_vals.get(ch, np.nan)
        if not np.isnan(db_val):
            coords.append(pos)
            if interp_space == 'pa':
                vals.append(10**(db_val/20) * 2e-5)
            elif interp_space == 'log':
                vals.append(np.log10(10**(db_val/20) * 2e-5 + 1e-12))
            else:
                vals.append(db_val)

    coords = np.array(coords)
    vals = np.array(vals)

    # 2. Paramètres physiques
    c = 343.0
    lam = c / freq
    tree_micros = cKDTree(coords)
    dists_micros, _ = tree_micros.query(coords, k=2)
    spacing = np.mean(dists_micros[:, 1])

    # 3. Interpolateur RBF global
    kernel = 'thin_plate_spline' if method == 'thin_plate' else method
    epsilon = spacing * 1.2

    interp = RBFInterpolator(
        coords, vals,
        kernel=kernel,
        smoothing=smoothing,
        epsilon=epsilon if method != 'thin_plate' else None
    )

    # 4. Grille 3D complète
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds

    Xv, Yv, Zv = np.meshgrid(
        np.linspace(x_min, x_max, resolution),
        np.linspace(y_min, y_max, resolution),
        np.linspace(z_min, z_max, resolution),
        indexing='ij'
    )

    flat_grid = np.column_stack([Xv.ravel(), Yv.ravel(), Zv.ravel()])

    # 5. Interpolation sur tout le volume
    res_flat = interp(flat_grid)
    res_vol = res_flat.reshape(Xv.shape)

    # 6. Conversion vers dB SPL
    if interp_space == 'pa':
        res_db = 20 * np.log10(np.maximum(res_vol, 1e-12) / 2e-5)
    elif interp_space == 'log':
        res_db = 20 * np.log10(10**res_vol / 2e-5)
    else:
        res_db = res_vol

    # 7. Masquage global par distance
    if max_distance:
        dists, _ = tree_micros.query(flat_grid, k=1)
        mask = dists.reshape(res_vol.shape) > max_distance
        res_db[mask] = np.nan

    # 8. Lissage 3D global
    side_length = max(x_max-x_min, y_max-y_min, z_max-z_min)
    pixel_size = side_length / resolution
    sigma_px = (lam / 4) / pixel_size if freq > 0 else 0

    if sigma_px > 0.5:
        nan_mask = np.isnan(res_db)
        if nan_mask.any():
            temp = np.where(nan_mask, np.nanmean(res_db), res_db)
            temp = gaussian_filter(temp, sigma=sigma_px, mode='nearest')
            res_db = np.where(nan_mask, np.nan, temp)
        else:
            res_db = gaussian_filter(res_db, sigma=sigma_px, mode='nearest')

    # 9. Extraction des 6 faces (continuité garantie)
    faces_results = []

    faces_results.append((Xv[0,:,:], Yv[0,:,:], Zv[0,:,:], res_db[0,:,:]))       # x = min
    faces_results.append((Xv[-1,:,:], Yv[-1,:,:], Zv[-1,:,:], res_db[-1,:,:]))   # x = max

    faces_results.append((Xv[:,0,:], Yv[:,0,:], Zv[:,0,:], res_db[:,0,:]))       # y = min
    faces_results.append((Xv[:,-1,:], Yv[:,-1,:], Zv[:,-1,:], res_db[:,-1,:]))   # y = max

    faces_results.append((Xv[:,:,0], Yv[:,:,0], Zv[:,:,0], res_db[:,:,0]))       # z = min
    faces_results.append((Xv[:,:,-1], Yv[:,:,-1], Zv[:,:,-1], res_db[:,:,-1]))   # z = max

    return faces_results


def plot_mems_3d(
    db_vals,
    chan_to_pos,
    geo_positions,
    config,
    mode='smooth',           # 'smooth', 'mesh', ou None
    show_mics=True,          # remplace show_spheres
    alphaa=0.95,
    dynamic_dB=20,
    method='thin_plate',
    interp_space='log'
):
    """
    Affiche en 3D les niveaux SPL mesurés par les MEMS sur les faces du cube.

    Paramètres
    ----------
    db_vals : dict
        {canal : valeur SPL en dB}
    chan_to_pos : dict
        {canal : (x,y,z)}
    geo_positions : ndarray Nx3
    config : objet configuration globale
    mode : None → seulement les micros
           'mesh' → interpolation IDW face par face
           'smooth' → interpolation RBF globale
    show_mics : bool
        Affiche les micros (sphères)
    """

    # ======================================================================
    # 1. Préparation limites & normalisation couleurs
    # ======================================================================
    bounds, norm = prepare_plot_data(db_vals, geo_positions, config, dynamic_dB)
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds

    # ======================================================================
    # 2. Création figure 3D
    # ======================================================================
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    cmap = plt.cm.jet

    # ======================================================================
    # 3. Affichage des surfaces (si demandé)
    # ======================================================================
    if mode in ['mesh', 'smooth']:

        title = plot_surfaces(
            ax=ax,
            mode=mode,
            db_vals=db_vals,
            chan_to_pos=chan_to_pos,
            geo_positions=geo_positions,
            config=config,
            norm=norm,
            alphaa=alphaa,
            method=method,
            interp_space=interp_space
        )

    else:
        # Aucun affichage de surface → seulement les micros
        title = "Positions MEMS (pas d’interpolation)"

    # ======================================================================
    # 4. Affichage des micros si demandé
    # ======================================================================
    if show_mics:
        plot_micro_spheres(ax, db_vals, chan_to_pos, bounds, config, norm)

    # ======================================================================
    # 5. Arêtes du cube
    # ======================================================================
    plot_cube_edges(ax, bounds)

    # ======================================================================
    # 6. Boutons de vue
    # ======================================================================
    add_view_buttons(fig, ax)

    # ======================================================================
    # 7. Colorbar (si surfaces ou valeurs)
    # ======================================================================
    valid_vals = np.array([v for v in db_vals.values() if not np.isnan(v)])
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array(valid_vals)
    cbar = fig.colorbar(mappable, ax=ax, shrink=0.6, pad=0.08)
    cbar.set_label('SPL (dB)', fontsize=10)

    # ======================================================================
    # 8. Mise en forme
    # ======================================================================
    ax.set_title(title, fontsize=12, weight='bold')
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_zlabel('Z [m]')

    ax.set_xlim([x_min - 0.02, x_max + 0.02])
    ax.set_ylim([y_min - 0.02, y_max + 0.02])
    ax.set_zlim([z_min - 0.02, z_max + 0.02])

    ax.set_proj_type('ortho')
    ax.dist = 9

    return fig, ax


def plot_third_octave_bars(all_results, mic_list, title="Tiers d’octave - Micros sélectionnés"):
    """
    Affiche un histogramme comparatif des niveaux tiers d'octave (corrigés)
    pour une liste de micros, avec leur niveau global.

    Paramètres
    ----------
    all_results : dict
        Résultats de compute_all_mems_spectra[ch] = {...}
    mic_list : list
        Liste des micros à afficher (ex: [1, 5, 12])
    title : str
        Titre du graphique
    """

    plt.figure(figsize=(12, 6))

    # largeur auto-adaptée selon le nombre de micros
    width = 0.8 / len(mic_list)
    colors = plt.cm.tab10.colors

    # On suppose que tous les micros ont les mêmes bandes
    ref_mic = mic_list[0]
    bands = all_results[ref_mic]['bands']
    idx = np.arange(len(bands))

    for i, mic in enumerate(mic_list):

        data = all_results[mic]
        bands = data['bands']
        levels = data['levels_corr']

        # Conversion en dB SPL
        levels_db = 20 * np.log10(levels / 2e-5)

        # Niveau global
        valid = ~np.isnan(levels_db)
        L_global = 10 * np.log10(np.sum(10**(levels_db[valid] / 10)))

        print(f"\n Micro {mic} → Global = {L_global:.2f} dB")

        # Décalage horizontal pour éviter la superposition
        offset = (i - len(mic_list) / 2) * width

        # Barres par bande
        plt.bar(idx + offset,
                levels_db,
                width=width,
                color=colors[i % len(colors)],
                edgecolor='k',
                label=f"Mic {mic}")

        # Barre du niveau global
        plt.bar(len(bands) + offset,
                L_global,
                width=width,
                color=colors[i % len(colors)],
                edgecolor='k')

    # ================================
    # AXES
    # ================================
    plt.xticks(
        list(np.arange(len(bands))) + [len(bands)],
        [f"{int(f)}" for f in bands] + ['Global'],
        rotation=45
    )

    plt.ylabel("Niveau [dB SPL]")
    plt.xlabel("Fréquence [Hz]")
    plt.title(title)
    plt.grid(True, ls='--', lw=0.5)
    plt.legend(title="Micros")

    plt.tight_layout()
    plt.show()


