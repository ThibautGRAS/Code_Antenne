# -*- coding: utf-8 -*-
"""
Created on Wed Nov 26 10:50:07 2025

@author: gras
"""

import os

import numpy as np

# Backend interactif par defaut (sans ecraser un choix amont, ex. live -> Agg).
os.environ.setdefault("MPLBACKEND", "Qt5Agg")
import matplotlib.pyplot as plt

from src.visu import get_cube_bounds



# ============================================================================
# UTILITAIRES PUISSANCE ACOUSTIQUE
# ============================================================================

def plot_acoustic_power_on_cube(db_vals, chan_to_pos, geo_positions, config,
                                n_subsurf_per_face=4, rho=1.21, c=343):
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize, to_rgba
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    # -----------------------------
    # Outil : appartenance à un bin
    # [a,b[ sauf dernier bin : [a,b]
    # -----------------------------
    def in_bin(v, a, b, is_last=False, tol=1e-12):
        if is_last:
            return (v >= a - tol) and (v <= b + tol)
        return (v >= a - tol) and (v < b - tol)

    # Conversion dB -> Pa
    pa_vals = {
        ch: 20e-6 * 10**(db / 20) if not np.isnan(db) else np.nan
        for ch, db in db_vals.items()
    }

    (x_min, x_max), (y_min, y_max), (z_min, z_max) = get_cube_bounds(geo_positions)

    faces = [
        ('x', x_min, (y_min, y_max), (z_min, z_max)),
        ('x', x_max, (y_min, y_max), (z_min, z_max)),
        ('y', y_min, (x_min, x_max), (z_min, z_max)),
        ('y', y_max, (x_min, x_max), (z_min, z_max)),
        ('z', z_max, (x_min, x_max), (y_min, y_max)),
    ]

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')

    all_face_powers = []

    cmap = plt.cm.jet
    temp_W_db = []

    tol_face = 1e-9

    # -----------------------------
    # 1ère passe : min/max couleur
    # -----------------------------
    for ftype, c_fixed, range1, range2 in faces:
        grid1 = np.linspace(range1[0], range1[1], n_subsurf_per_face + 1)
        grid2 = np.linspace(range2[0], range2[1], n_subsurf_per_face + 1)

        for i in range(n_subsurf_per_face):
            for j in range(n_subsurf_per_face):
                r1_0, r1_1 = grid1[i], grid1[i + 1]
                r2_0, r2_1 = grid2[j], grid2[j + 1]

                is_last_i = (i == n_subsurf_per_face - 1)
                is_last_j = (j == n_subsurf_per_face - 1)

                if ftype == 'x':
                    values = [
                        pa_vals[ch]
                        for ch, (xm, ym, zm) in chan_to_pos.items()
                        if np.isclose(xm, c_fixed, atol=tol_face)
                        and in_bin(ym, r1_0, r1_1, is_last_i)
                        and in_bin(zm, r2_0, r2_1, is_last_j)
                        and np.isfinite(pa_vals[ch])
                    ]

                elif ftype == 'y':
                    values = [
                        pa_vals[ch]
                        for ch, (xm, ym, zm) in chan_to_pos.items()
                        if np.isclose(ym, c_fixed, atol=tol_face)
                        and in_bin(xm, r1_0, r1_1, is_last_i)
                        and in_bin(zm, r2_0, r2_1, is_last_j)
                        and np.isfinite(pa_vals[ch])
                    ]

                else:  # ftype == 'z'
                    values = [
                        pa_vals[ch]
                        for ch, (xm, ym, zm) in chan_to_pos.items()
                        if np.isclose(zm, c_fixed, atol=tol_face)
                        and in_bin(xm, r1_0, r1_1, is_last_i)
                        and in_bin(ym, r2_0, r2_1, is_last_j)
                        and np.isfinite(pa_vals[ch])
                    ]

                if len(values) > 0:
                    p_rms2 = np.mean(np.array(values) ** 2)
                    Si = (r1_1 - r1_0) * (r2_1 - r2_0)
                    W = p_rms2 / (rho * c) * Si
                    if W > 0:
                        temp_W_db.append(10 * np.log10(W / 1e-12))

    if len(temp_W_db) > 0:
        norm = Normalize(vmin=min(temp_W_db), vmax=max(temp_W_db))
    else:
        norm = Normalize(0, 1)

    # -----------------------------
    # 2e passe : calcul + tracé
    # -----------------------------
    for ftype, c_fixed, range1, range2 in faces:
        grid1 = np.linspace(range1[0], range1[1], n_subsurf_per_face + 1)
        grid2 = np.linspace(range2[0], range2[1], n_subsurf_per_face + 1)
        face_power = 0.0

        for i in range(n_subsurf_per_face):
            for j in range(n_subsurf_per_face):
                r1_0, r1_1 = grid1[i], grid1[i + 1]
                r2_0, r2_1 = grid2[j], grid2[j + 1]

                is_last_i = (i == n_subsurf_per_face - 1)
                is_last_j = (j == n_subsurf_per_face - 1)

                Si = (r1_1 - r1_0) * (r2_1 - r2_0)

                if ftype == 'x':
                    values = [
                        pa_vals[ch]
                        for ch, (xm, ym, zm) in chan_to_pos.items()
                        if np.isclose(xm, c_fixed, atol=tol_face)
                        and in_bin(ym, r1_0, r1_1, is_last_i)
                        and in_bin(zm, r2_0, r2_1, is_last_j)
                        and np.isfinite(pa_vals[ch])
                    ]
                    verts = [[c_fixed, r1_0, r2_0],
                             [c_fixed, r1_1, r2_0],
                             [c_fixed, r1_1, r2_1],
                             [c_fixed, r1_0, r2_1]]

                elif ftype == 'y':
                    values = [
                        pa_vals[ch]
                        for ch, (xm, ym, zm) in chan_to_pos.items()
                        if np.isclose(ym, c_fixed, atol=tol_face)
                        and in_bin(xm, r1_0, r1_1, is_last_i)
                        and in_bin(zm, r2_0, r2_1, is_last_j)
                        and np.isfinite(pa_vals[ch])
                    ]
                    verts = [[r1_0, c_fixed, r2_0],
                             [r1_1, c_fixed, r2_0],
                             [r1_1, c_fixed, r2_1],
                             [r1_0, c_fixed, r2_1]]

                else:  # ftype == 'z'
                    values = [
                        pa_vals[ch]
                        for ch, (xm, ym, zm) in chan_to_pos.items()
                        if np.isclose(zm, c_fixed, atol=tol_face)
                        and in_bin(xm, r1_0, r1_1, is_last_i)
                        and in_bin(ym, r2_0, r2_1, is_last_j)
                        and np.isfinite(pa_vals[ch])
                    ]
                    verts = [[r1_0, r2_0, c_fixed],
                             [r1_1, r2_0, c_fixed],
                             [r1_1, r2_1, c_fixed],
                             [r1_0, r2_1, c_fixed]]

                if len(values) == 0:
                    W_db = np.nan
                else:
                    p_rms2 = np.mean(np.array(values) ** 2)
                    W = p_rms2 / (rho * c) * Si
                    face_power += W
                    W_db = 10 * np.log10(W / 1e-12) if W > 0 else np.nan

                if np.isnan(W_db):
                    poly = Poly3DCollection(
                        [verts],
                        facecolor=to_rgba('grey', 0.0),
                        edgecolor='k',
                        linewidth=0.5,
                        alpha=0.3
                    )
                else:
                    poly = Poly3DCollection(
                        [verts],
                        facecolor=cmap(norm(W_db)),
                        edgecolor='k',
                        linewidth=0.5,
                        alpha=0.8
                    )

                ax.add_collection3d(poly)

        all_face_powers.append(face_power)

    all_face_powers = np.array(all_face_powers, dtype=float)
    total_power = np.nansum(all_face_powers)

    all_face_db = np.full_like(all_face_powers, np.nan, dtype=float)
    valid_faces = all_face_powers > 0
    all_face_db[valid_faces] = 10 * np.log10(all_face_powers[valid_faces] / 1e-12)

    total_power_db = 10 * np.log10(total_power / 1e-12) if total_power > 0 else np.nan

    ax.set_title(
        f"Puissance acoustique par sous-face\n"
        f"| Bande {config.chosen_band:.0f} Hz | Total: {total_power_db:.1f} dB",
        fontsize=14
    )
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_zlabel('Z [m]')
    ax.set_xlim([x_min - 0.05, x_max + 0.05])
    ax.set_ylim([y_min - 0.05, y_max + 0.05])
    ax.set_zlim([0, z_max + 0.05])

    cbar = fig.colorbar(
        plt.cm.ScalarMappable(norm=norm, cmap=cmap),
        ax=ax,
        shrink=0.7,
        pad=0.1
    )
    cbar.set_label('Niveau de puissance [dB]', fontsize=12)

    return fig, ax, all_face_db, total_power_db

def acoustic_power_faces(all_results, chan_to_pos, rho=1.21, c=343, trace_total_only=False):
    """
    Calcule la puissance acoustique par face principale (top/front/left/right/back)
    et totale pour chaque fréquence tiers d'octave, en tenant compte
    de la surface des faces principales.

    Trace :
      - Si trace_total_only=False : courbes pour chaque face + total
      - Si trace_total_only=True : histogramme total par fréquence + barre globale 20-20kHz

    Paramètres :
        all_results : dict {ch: {'bands','levels_corr'}}
        chan_to_pos : dict {ch: (x,y,z)}
        rho, c : masse volumique et vitesse du son
        trace_total_only : bool, histogramme total ou courbes faces+total

    Retour :
        fig, ax : figure et axes matplotlib
        W_dB_faces : dict {face: array puissance dB par fréquence}
        W_total_dB : array puissance totale dB par fréquence
        W_total_global_dB : valeur globale en dB (somme énergétique sur toutes fréquences)
    """

    # Détection faces principales
    positions = np.array(list(chan_to_pos.values()))
    x_min, x_max = positions[:,0].min(), positions[:,0].max()
    y_min, y_max = positions[:,1].min(), positions[:,1].max()
    z_min, z_max = positions[:,2].min(), positions[:,2].max()

    # surfaces des faces principales
    S_faces = {
        'front':  (x_max - x_min)*(z_max - z_min),
        'back':   (x_max - x_min)*(z_max - z_min),
        'left':   (y_max - y_min)*(z_max - z_min),
        'right':  (y_max - y_min)*(z_max - z_min),
        'top':    (x_max - x_min)*(y_max - y_min)
    }

    # conditions pour sélectionner les MEMS de chaque face
    faces = {
        'front':  lambda x,y,z: np.isclose(y, y_min),
        'back':   lambda x,y,z: np.isclose(y, y_max),
        'left':   lambda x,y,z: np.isclose(x, x_min),
        'right':  lambda x,y,z: np.isclose(x, x_max),
        'top':    lambda x,y,z: np.isclose(z, z_max)
    }

    # fréquences tiers d'octave
    sample_ch = next(iter(all_results.values()))
    freqs = sample_ch['bands']

    W_faces = {face: [] for face in faces}
    W_total = []

    # Calcul de la puissance par face
    for fi, f in enumerate(freqs):
        W_f = {}
        for face, cond in faces.items():
            vals = [all_results[ch]['levels_corr'][fi] for ch, pos in chan_to_pos.items()
                    if cond(*pos)]
            if len(vals) == 0:
                W_f[face] = np.nan
            else:
                p_rms2 = np.mean(np.array(vals)**2)
                W_f[face] = p_rms2 / (rho*c) * S_faces[face]
            W_faces[face].append(W_f[face])

        W_vals = np.array([w for w in W_f.values() if not np.isnan(w)])
        W_total.append(np.sum(W_vals))

    # Conversion en dB
    W_dB_faces = {face: 10*np.log10(np.array(W_faces[face])/1e-12) for face in faces}
    W_total_dB = 10*np.log10(np.array(W_total)/1e-12)
    W_total_global_dB = 10*np.log10(np.nansum(np.array(W_total))/1e-12)

    # Tracé
    fig, ax = plt.subplots(figsize=(12,6))

    if trace_total_only:
        # indices pour la bande 20 Hz - 20 kHz
        idx_band = np.where((freqs >= 20) & (freqs <= 20000))[0]
    
        # Histogramme sur cette bande
        ax.bar(np.arange(len(idx_band)), W_total_dB[idx_band], color='#32cd32', edgecolor='k')
    
        # Calcul puissance globale sur cette bande
        W_total_band = np.nansum(10**(W_total_dB[idx_band]/10))
        W_total_band_dB = 10*np.log10(W_total_band)
    
        # Ajouter dernière barre pour valeur globale
        ax.bar(len(idx_band), W_total_band_dB, color='salmon', edgecolor='k', label='Total global')
    
        # xticks et labels
        ax.set_xticks(list(np.arange(len(idx_band))) + [len(idx_band)])
        ax.set_xticklabels([f"{int(freqs[i])}" for i in idx_band] + ['Global'], rotation=45)
        
        W_min = np.floor(np.nanmin(W_total_dB[idx_band])/10)*10  # min arrondi à 10 dB
        W_max = np.ceil((W_total_band_dB)/10)*10   # max arrondi à 10 dB
        yticks = np.arange(W_min, W_max+1, 10)
        
        ax.set_ylim([W_min, W_max])
        ax.set_yticks(yticks)
    
        ax.set_xlabel('Fréquence [Hz]')
        ax.set_ylabel('Puissance acoustique [dB]')
        ax.set_title('Puissance totale par fréquence (20 Hz - 20 kHz)')
        ax.grid(True, which='both', ls='--', lw=0.5)
        ax.legend()

    else:
        # Courbes pour chaque face + total
        colors = {'front':'r','back':'b','left':'g','right':'m','top':'c'}
        for face, WdB in W_dB_faces.items():
            ax.plot(freqs, WdB, label=face, color=colors[face])
        ax.plot(freqs, W_total_dB, 'k--', linewidth=2, label='Total')
        ax.set_xscale('log')
        ax.set_xlabel('Fréquence [Hz]')
        ax.set_ylabel('Puissance acoustique [dB]')
        ax.set_title('Puissance acoustique par face principale')
        ax.grid(True, which='both', ls='--', lw=0.5)
        ax.legend()

    plt.tight_layout()
    return fig, ax, W_dB_faces, W_total_dB, W_total_global_dB, freqs

def plot_power_comparison(freq,
                          W_mems_dB,
                          exp_file,
                          label_mems="MEMS",
                          label_exp="MICROPHONES",
                          fmin=100,
                          fmax=20000):
    """
    Compare puissance acoustique MEMS vs EXP
    avec histogrammes côte à côte + niveau global.

    Parameters
    ----------
    freq : array
        Fréquences centrales des bandes MEMS
    W_mems_dB : array
        Niveaux de puissance MEMS par bande [dB]
    exp_file : str
        Fichier txt avec 2 colonnes : freq [Hz], niveau [dB]
    label_mems : str
        Label légende MEMS
    label_exp : str
        Label légende EXP
    fmin : float
        Fréquence minimale à afficher
    fmax : float
        Fréquence maximale à afficher
    """

    import numpy as np
    import matplotlib.pyplot as plt

    freq = np.asarray(freq, dtype=float)
    W_mems_dB = np.asarray(W_mems_dB, dtype=float)

    # =========================
    # LOAD EXP DATA
    # =========================
    data_exp = np.loadtxt(exp_file, skiprows=1)
    freq_exp = data_exp[:, 0]
    W_exp_dB = data_exp[:, 1]

    # =========================
    # PROJECTION EXP -> bandes MEMS
    # =========================
    W_exp_band = []

    for f_c in freq:
        f_low = f_c / (2**(1/6))
        f_high = f_c * (2**(1/6))

        idx = (freq_exp >= f_low) & (freq_exp <= f_high)

        if np.any(idx):
            val = 10 * np.log10(np.mean(10**(W_exp_dB[idx] / 10)))
        else:
            val = np.nan

        W_exp_band.append(val)

    W_exp_band = np.asarray(W_exp_band, dtype=float)

    # =========================
    # FILTRE D'AFFICHAGE
    # =========================
    idx_keep = (freq >= fmin) & (freq <= fmax)

    freq_plot = freq[idx_keep]
    W_mems_plot = W_mems_dB[idx_keep]
    W_exp_plot = W_exp_band[idx_keep]

    x = np.arange(len(freq_plot))
    width = 0.35
    x_global = len(freq_plot) + 1

    # =========================
    # GLOBAL LEVEL
    # =========================
    def global_level(W):
        valid = np.isfinite(W)
        if not np.any(valid):
            return np.nan
        return 10 * np.log10(np.sum(10**(W[valid] / 10)))

    L_mems_global = global_level(W_mems_plot)
    L_exp_global = global_level(W_exp_plot)

    # =========================
    # PLOT
    # =========================
    fig, ax = plt.subplots(figsize=(12, 6))

    ax.bar(x - width/2, W_mems_plot,
           width=width, color='blue', edgecolor='k', label=f"{label_mems} : {L_mems_global:.2f} dB")

    ax.bar(x + width/2, W_exp_plot,
           width=width, color='orange', edgecolor='k', label=f"{label_exp}  : {L_exp_global:.2f} dB")

    # barres globales
    ax.bar(x_global - width/2, L_mems_global,
           width=width, color='blue', edgecolor='k')

    ax.bar(x_global + width/2, L_exp_global,
           width=width, color='orange', edgecolor='k')

    # ticks
    xticks = list(x) + [x_global]
    xticklabels = [f"{int(f)}" for f in freq_plot] + ["Global"]

    ax.set_xticks(xticks)
    ax.set_xticklabels(xticklabels, rotation=45)

    ax.set_xlim(-0.8, x_global + 0.8)
    ax.set_ylim([50 ,105])

    ax.set_xlabel("Frequency [Hz]")
    ax.set_ylabel("Acoustic Power [dB]")
    
    ax.grid(True, ls='--', alpha=0.5)
    ax.legend()
    
    # =========================
    # ANNOTATIONS DES ÉCARTS
    # =========================
    delta_band = W_mems_plot - W_exp_plot
    
    for i, d in enumerate(delta_band):
        if np.isfinite(d) and np.isfinite(W_mems_plot[i]) and np.isfinite(W_exp_plot[i]):
            y_text = max(W_mems_plot[i], W_exp_plot[i]) + 0.8
    
            if np.abs(d) > 1:
                color_txt = 'red'
            elif np.abs(d) < 1:
                color_txt = 'blue'
            else:
                color_txt = 'black'
    
            ax.text(i, y_text, f"{d:+.1f}",
                    ha='center', va='bottom',
                    fontsize=8, color=color_txt, rotation=0,fontweight='bold')
    
    # annotation globale
    delta_global = L_mems_global - L_exp_global
    if np.isfinite(delta_global):
        y_text_global = max(L_mems_global, L_exp_global) + 1.0
    
        if np.abs(delta_global) > 1:
            color_txt = 'red'
        elif np.abs(delta_global) < 1:
            color_txt = 'blue'
        else:
            color_txt = 'black'
    
        ax.text(x_global, y_text_global, f"{delta_global:+.1f}",
                ha='center', va='bottom',
                fontsize=9, color=color_txt, fontweight='bold')

    plt.tight_layout()
    plt.show()

    # =========================
    # PRINT INFO
    # =========================
    print("\n === Comparaison power niveau GLOBAL ===")
    print(f"{label_mems} : {L_mems_global:.2f} dB")
    print(f"{label_exp}  : {L_exp_global:.2f} dB")
    print(f"Δ (MEMS - EXP) : {L_mems_global - L_exp_global:.2f} dB")

    return fig, ax, freq_plot, W_mems_plot, W_exp_plot, L_mems_global, L_exp_global
        

def acoustic_power_selected_mems_hist(
    all_results,
    chan_to_pos,
    cube_Lx,
    cube_Ly,
    cube_Lz,
    surface_totale,
    origin=(0, 0, 0),
    rho=1.21,
    c=343,
    mode="center5",                 # "center5", "custom", "center5_topcorners"
    custom_mics=None,               # ex: [12, 45, 88, 120, 156]
    tol=0.05,                       # tolérance pour appartenir à une face
    show_3d=True,
    compare_exp_file=None,          # ex: "POWER_SOURCE.txt"
    label_mems="MEMS",
    label_exp="MICROPHONES",
    fmin_compare=100,
    fmax_compare=20000,
    show_compare=True
):
    """
    Estimation de puissance acoustique par sélection d'un sous-ensemble de MEMS.

    Philosophie :
    - on sélectionne des MEMS représentatifs
    - on calcule <p^2> sur ces MEMS
    - on estime W = <p^2> / (rho*c) * S_total

    Modes
    -----
    mode="center5"
        5 MEMS : centres des 5 faces mesurées
    mode="custom"
        MEMS définis par custom_mics
    mode="center5_topcorners"
        5 centres de faces + 4 coins supérieurs du dessus

    Paramètres additionnels
    -----------------------
    compare_exp_file : str or None
        Fichier txt de référence externe à comparer
    label_mems : str
        Label du jeu MEMS
    label_exp : str
        Label du fichier texte
    fmin_compare, fmax_compare : float
        Plage fréquentielle pour le graphe de comparaison
    show_compare : bool
        Affiche ou non le graphe de comparaison si compare_exp_file est fourni

    Returns
    -------
    freqs : ndarray
    W_total_dB : ndarray
    W_global_dB : float
    selected_mics : dict
    fig, ax : figure histogramme MEMS
    fig3d, ax3d : figure 3D
    compare_results : dict or None
    """

    import numpy as np
    import matplotlib.pyplot as plt

    # =========================================================
    # fonction interne de comparaison avec fichier texte
    # =========================================================
    def plot_power_comparison(freq,
                              W_mems_dB,
                              exp_file,
                              label_mems="MEMS",
                              label_exp="MICROPHONES",
                              fmin=100,
                              fmax=20000):
        freq = np.asarray(freq, dtype=float)
        W_mems_dB = np.asarray(W_mems_dB, dtype=float)

        # LOAD EXP DATA
        data_exp = np.loadtxt(exp_file, skiprows=1)
        freq_exp = data_exp[:, 0]
        W_exp_dB = data_exp[:, 1]

        # PROJECTION EXP -> bandes MEMS
        W_exp_band = []
        for f_c in freq:
            f_low = f_c / (2**(1/6))
            f_high = f_c * (2**(1/6))

            idx = (freq_exp >= f_low) & (freq_exp <= f_high)

            if np.any(idx):
                val = 10 * np.log10(np.mean(10**(W_exp_dB[idx] / 10)))
            else:
                val = np.nan

            W_exp_band.append(val)

        W_exp_band = np.asarray(W_exp_band, dtype=float)

        # FILTRE D'AFFICHAGE
        idx_keep = (freq >= fmin) & (freq <= fmax)

        freq_plot = freq[idx_keep]
        W_mems_plot = W_mems_dB[idx_keep]
        W_exp_plot = W_exp_band[idx_keep]

        x = np.arange(len(freq_plot))
        width = 0.35
        x_global = len(freq_plot) + 1

        def global_level(W):
            valid = np.isfinite(W)
            if not np.any(valid):
                return np.nan
            return 10 * np.log10(np.sum(10**(W[valid] / 10)))

        L_mems_global = global_level(W_mems_plot)
        L_exp_global = global_level(W_exp_plot)

        fig_cmp, ax_cmp = plt.subplots(figsize=(12, 6))

        ax_cmp.bar(x - width/2, W_mems_plot,
                   width=width, color='green', edgecolor='k', label=(f"{label_mems} : {L_mems_global:.2f} dB"))

        ax_cmp.bar(x + width/2, W_exp_plot,
                   width=width, color='orange', edgecolor='k', label=f"{label_exp}  : {L_exp_global:.2f} dB")

        ax_cmp.bar(x_global - width/2, L_mems_global,
                   width=width, color='green', edgecolor='k')

        ax_cmp.bar(x_global + width/2, L_exp_global,
                   width=width, color='orange', edgecolor='k')

        xticks = list(x) + [x_global]
        xticklabels = [f"{int(f)}" for f in freq_plot] + ["Global"]

        ax_cmp.set_xticks(xticks)
        ax_cmp.set_xticklabels(xticklabels, rotation=45)
        ax_cmp.set_xlim(-0.8, x_global + 0.8)
        
        

        ax_cmp.set_xlabel("Frequency [Hz]")
        ax_cmp.set_ylabel("Acoustic Power [dB]")
        ax_cmp.grid(True, ls='--', alpha=0.5)
        ax_cmp.legend()

        # annotations des écarts
        delta_band = W_mems_plot - W_exp_plot

        for i, d in enumerate(delta_band):
            if np.isfinite(d) and np.isfinite(W_mems_plot[i]) and np.isfinite(W_exp_plot[i]):
                y_text = max(W_mems_plot[i], W_exp_plot[i]) + 0.8

                if np.abs(d) > 1:
                    color_txt = 'red'
                elif np.abs(d) < 1:
                    color_txt = 'blue'
                else:
                    color_txt = 'black'

                ax_cmp.text(i, y_text, f"{d:+.1f}",
                            ha='center', va='bottom',
                            fontsize=8, color=color_txt, rotation=0, fontweight='bold')

        delta_global = L_mems_global - L_exp_global
        if np.isfinite(delta_global):
            y_text_global = max(L_mems_global, L_exp_global) + 1.0

            if np.abs(delta_global) > 1:
                color_txt = 'red'
            elif np.abs(delta_global) < 1:
                color_txt = 'blue'
            else:
                color_txt = 'black'

            ax_cmp.text(x_global, y_text_global, f"{delta_global:+.1f}",
                        ha='center', va='bottom',
                        fontsize=9, color=color_txt, fontweight='bold')
            
            ax_cmp.set_ylim([50 ,105])

        plt.tight_layout()

        print("=== GLOBAL COMPARISON ===")
        print(f"{label_mems} : {L_mems_global:.2f} dB")
        print(f"{label_exp}  : {L_exp_global:.2f} dB")
        print(f"Δ ({label_mems} - {label_exp}) : {L_mems_global - L_exp_global:.2f} dB")

        return {
            "fig_compare": fig_cmp,
            "ax_compare": ax_cmp,
            "freq_plot": freq_plot,
            "W_mems_plot": W_mems_plot,
            "W_exp_plot": W_exp_plot,
            "L_mems_global": L_mems_global,
            "L_exp_global": L_exp_global,
            "delta_global": L_mems_global - L_exp_global
        }

    # =========================================================
    # 1) Géométrie réelle du cube
    # =========================================================
    x0, y0, z0 = origin

    x_min, x_max = x0, x0 + cube_Lx
    y_min, y_max = y0, y0 + cube_Ly
    z_min, z_max = z0, z0 + cube_Lz

    # =========================================================
    # 2) Outils sélection
    # =========================================================
    def nearest_mic_on_filtered_set(target, cond, axes=(0, 1, 2), forbidden=None):
        if forbidden is None:
            forbidden = set()

        candidates = [
            (ch, pos) for ch, pos in chan_to_pos.items()
            if cond(*pos) and (ch not in forbidden)
        ]

        if len(candidates) == 0:
            return None

        positions = np.array([pos for _, pos in candidates], dtype=float)
        target_arr = np.array(target, dtype=float)

        dists = np.linalg.norm(
            positions[:, list(axes)] - target_arr[list(axes)],
            axis=1
        )

        idx = np.argmin(dists)
        return candidates[idx][0]

    def build_center5_selection():
        selected = {}
        used = set()

        face_defs = {
            'xmin': {
                'target': (x_min, 0.5*(y_min+y_max), 0.5*(z_min+z_max)),
                'cond':   lambda x, y, z: abs(x - x_min) < tol,
                'axes':   (1, 2)
            },
            'xmax': {
                'target': (x_max, 0.5*(y_min+y_max), 0.5*(z_min+z_max)),
                'cond':   lambda x, y, z: abs(x - x_max) < tol,
                'axes':   (1, 2)
            },
            'ymin': {
                'target': (0.5*(x_min+x_max), y_min, 0.5*(z_min+z_max)),
                'cond':   lambda x, y, z: abs(y - y_min) < tol,
                'axes':   (0, 2)
            },
            'ymax': {
                'target': (0.5*(x_min+x_max), y_max, 0.5*(z_min+z_max)),
                'cond':   lambda x, y, z: abs(y - y_max) < tol,
                'axes':   (0, 2)
            },
            'zmax': {
                'target': (0.5*(x_min+x_max), 0.5*(y_min+y_max), z_max),
                'cond':   lambda x, y, z: abs(z - z_max) < tol,
                'axes':   (0, 1)
            },
        }

        for label, d in face_defs.items():
            ch = nearest_mic_on_filtered_set(
                target=d['target'],
                cond=d['cond'],
                axes=d['axes'],
                forbidden=used
            )
            if ch is None:
                print(f"⚠️ Aucun micro trouvé pour {label}")
            else:
                selected[label] = ch
                used.add(ch)

        return selected, used

    def add_top_corners_selection(selected, used):
        top_cond = lambda x, y, z: abs(z - z_max) < tol

        corners = {
            'top_corner_1': (x_min, y_min, z_max),
            'top_corner_2': (x_max, y_min, z_max),
            'top_corner_3': (x_max, y_max, z_max),
            'top_corner_4': (x_min, y_max, z_max),
        }

        for label, target in corners.items():
            ch = nearest_mic_on_filtered_set(
                target=target,
                cond=top_cond,
                axes=(0, 1),
                forbidden=used
            )
            if ch is None:
                print(f"⚠️ Aucun micro trouvé pour {label}")
            else:
                selected[label] = ch
                used.add(ch)

        return selected, used

    # =========================================================
    # 3) Construction de la sélection
    # =========================================================
    if mode == "center5":
        selected_mics, used = build_center5_selection()

    elif mode == "center5_topcorners":
        selected_mics, used = build_center5_selection()
        selected_mics, used = add_top_corners_selection(selected_mics, used)

    elif mode == "custom":
        if custom_mics is None or len(custom_mics) == 0:
            raise ValueError("mode='custom' nécessite custom_mics=[...]")

        selected_mics = {}
        for k, ch in enumerate(custom_mics):
            if ch not in chan_to_pos:
                print(f"⚠️ Micro {ch} absent de chan_to_pos")
            else:
                selected_mics[f'custom_{k+1}'] = ch

    else:
        raise ValueError("mode doit être 'center5', 'custom' ou 'center5_topcorners'")

    if len(selected_mics) == 0:
        raise RuntimeError("Aucun micro selectionne.")

    print("\n=== MEMS selectiones ===")
    for label, ch in selected_mics.items():
        print(f"{label:15s} -> micro #{ch}")

    # =========================================================
    # 4) Calcul puissance par bande
    # =========================================================
    sample_ch = next(iter(all_results.values()))
    freqs = np.asarray(sample_ch['bands'], dtype=float)

    W_total = []

    for fi in range(len(freqs)):
        pressures = []

        for ch in selected_mics.values():
            val = all_results[ch]['levels_corr'][fi]
            if np.isfinite(val):
                pressures.append(val)

        if len(pressures) == 0:
            W_total.append(np.nan)
            continue

        pressures = np.asarray(pressures, dtype=float)
        p_rms2 = np.mean(pressures**2)

        W = p_rms2 / (rho * c) * surface_totale
        W_total.append(W)

    W_total = np.asarray(W_total, dtype=float)

    W_total_dB = np.full_like(W_total, np.nan, dtype=float)
    valid = W_total > 0
    W_total_dB[valid] = 10*np.log10(W_total[valid] / 1e-12)

    # =========================================================
    # 5) Puissance globale
    # =========================================================
    W_global = np.nansum(W_total)
    W_global_dB = 10*np.log10(W_global / 1e-12) if W_global > 0 else np.nan

    print(f"\nPuissance globale = {W_global_dB:.2f} dB")

    valid_db = np.isfinite(W_total_dB)
    if np.any(valid_db):
        W_min = np.floor(np.nanmin(W_total_dB[valid_db]) / 10) * 10
        W_max = np.ceil(max(np.nanmax(W_total_dB[valid_db]), W_global_dB) / 10) * 10
    else:
        W_min, W_max = 0, 100

    yticks = np.arange(W_min, W_max + 1, 10)

    # =========================================================
    # 6) Histogramme MEMS seul
    # =========================================================
    fig, ax = plt.subplots(figsize=(12, 6))

    idx = np.arange(len(freqs))
    x_global = len(freqs) + 1

    ax.bar(idx, W_total_dB, color='dodgerblue', edgecolor='k')
    ax.bar(x_global, W_global_dB, color='red', edgecolor='k', label='Global')

    ax.set_xticks(list(idx) + [x_global])
    ax.set_xticklabels([f"{int(f)}" for f in freqs] + ['Global'], rotation=45)

    ax.set_ylabel("Puissance acoustique [dB]")
    ax.set_title(
        f"Puissance acoustique ({mode})\n"
        f"Puissance globale = {W_global_dB:.2f} dB"
    )
    ax.grid(True, ls='--', lw=0.5)
    ax.legend()

    # ax.set_ylim([W_min, W_max])
    ax.set_yticks(yticks)

    # =========================================================
    # 7) Visu 3D
    # =========================================================
    fig3d, ax3d = None, None

    if show_3d:
        fig3d = plt.figure(figsize=(10, 8))
        ax3d = fig3d.add_subplot(111, projection='3d')

        all_pos = np.array(list(chan_to_pos.values()), dtype=float)
        ax3d.scatter(all_pos[:, 0], all_pos[:, 1], all_pos[:, 2],
                     color='black', alpha=0.15, s=15)

        sel_pos = np.array([chan_to_pos[ch] for ch in selected_mics.values()], dtype=float)
        ax3d.scatter(sel_pos[:, 0], sel_pos[:, 1], sel_pos[:, 2],
                     color='red', s=80)

        for label, ch in selected_mics.items():
            x, y, z = chan_to_pos[ch]
            ax3d.text(x, y, z, f"{ch}", fontsize=10, weight='bold')

        cube_edges = [
            [(x_min,y_min,z_min),(x_max,y_min,z_min)],
            [(x_max,y_min,z_min),(x_max,y_max,z_min)],
            [(x_max,y_max,z_min),(x_min,y_max,z_min)],
            [(x_min,y_max,z_min),(x_min,y_min,z_min)],
            [(x_min,y_min,z_max),(x_max,y_min,z_max)],
            [(x_max,y_min,z_max),(x_max,y_max,z_max)],
            [(x_max,y_max,z_max),(x_min,y_max,z_max)],
            [(x_min,y_max,z_max),(x_min,y_min,z_max)],
            [(x_min,y_min,z_min),(x_min,y_min,z_max)],
            [(x_max,y_min,z_min),(x_max,y_min,z_max)],
            [(x_max,y_max,z_min),(x_max,y_max,z_max)],
            [(x_min,y_max,z_min),(x_min,y_max,z_max)],
        ]

        for e in cube_edges:
            xs = [e[0][0], e[1][0]]
            ys = [e[0][1], e[1][1]]
            zs = [e[0][2], e[1][2]]
            ax3d.plot(xs, ys, zs, color='black', linewidth=1)

        ax3d.set_box_aspect([cube_Lx, cube_Ly, cube_Lz])
        ax3d.set_title(f"Sélection MEMS ({mode})")
        ax3d.set_xlabel("X [m]")
        ax3d.set_ylabel("Y [m]")
        ax3d.set_zlabel("Z [m]")

    # =========================================================
    # 8) Comparaison externe optionnelle
    # =========================================================
    compare_results = None

    if compare_exp_file is not None:
        compare_results = plot_power_comparison(
            freqs,
            W_total_dB,
            compare_exp_file,
            label_mems=label_mems,
            label_exp=label_exp,
            fmin=fmin_compare,
            fmax=fmax_compare
        )

        if not show_compare:
            plt.close(compare_results["fig_compare"])

    return (
        freqs,
        W_total_dB,
        W_global_dB,
        selected_mics,
        fig,
        ax,
        fig3d,
        ax3d,
        compare_results
    )