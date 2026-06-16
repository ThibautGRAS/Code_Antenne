# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 14:50:29 2026

@author: gras
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

from IPython.display import Audio
from scipy.io.wavfile import write

# ============================================================================
# UTILITAIRES BEAMFORMING - TIMEFOCUS
# ============================================================================

def time_domain_focusing(data, mic_positions, source_pos, Fe, config,
                         geo_positions, c=340.0,
                         face=None, tol=1e-3,
                         z_plane=None, R=1.0,
                         plot_selected=False):
    """
    Focalisation temporelle avec option plan réfléchissant (méthode des images)

    data : (M, Nt) signaux temporels
    mic_positions : (M,3)
    source_pos : (3,)
    Fe : fréquence d'échantillonnage
    c : vitesse du son
    face : '+X', '-X', '+Y', '-Y', '+Z', '-Z' (optionnel)
    tol : tolérance sélection face
    z_plane : position du plan réfléchissant (ex : 0.0) ou None
    R : coefficient de réflexion (réel ou complexe)
    plot_selected : affichage géométrie
    """

    # --- Reshape / normalisation ---
    Sigs_val = data.reshape((-1, config.NbVoies)).T
    data_m = Sigs_val[1:len(geo_positions)+1, :] / config.SMEMS

    # --- Sélection des micros par face ---
    selected_idx = np.arange(mic_positions.shape[0])
    if face is not None:
        axis = {'+X':0, '-X':0, '+Y':1, '-Y':1, '+Z':2, '-Z':2}[face]
        ref_val = (np.max if face.startswith('+') else np.min)(mic_positions[:, axis])
        selected_idx = np.where(np.abs(mic_positions[:, axis] - ref_val) <= tol)[0]

    data_m = data_m[selected_idx, :]
    mic_positions_sel = mic_positions[selected_idx, :]

    # --- Affichage optionnel ---
    if plot_selected:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.scatter(mic_positions[:,0], mic_positions[:,1], mic_positions[:,2],
                   color='gray', alpha=0.3, label='Tous micros')
        ax.scatter(mic_positions_sel[:,0], mic_positions_sel[:,1], mic_positions_sel[:,2],
                   color='red', label='Micros sélectionnés')
        ax.scatter(*source_pos, color='blue', marker='*', s=100, label='Source')
        ax.legend()
        plt.show()

    # --- Paramètres temporels ---
    M, Nt = data_m.shape
    t = np.arange(Nt) / Fe

    # --- Retards champ direct ---
    dist = np.linalg.norm(mic_positions_sel - source_pos, axis=1)
    delays = dist / c

    # --- Retards champ réfléchi ---
    if z_plane is not None:
        source_img = source_pos.copy()
        source_img[2] = 2*z_plane - source_pos[2]
        dist_img = np.linalg.norm(mic_positions_sel - source_img, axis=1)
        delays_img = dist_img / c

    # --- Reconstruction du signal focalisé ---
    focused_signal = np.zeros(Nt)

    for m in range(M):
        interp = interp1d(t, data_m[m], kind='linear',
                          fill_value=0.0, bounds_error=False)

        # champ direct
        focused_signal += interp(t + delays[m])

        # champ réfléchi
        if z_plane is not None:
            focused_signal += np.real(R) * interp(t + delays_img[m])

    return focused_signal, mic_positions_sel


def save_focused_wav(filename, signal, Fe):
    # Normalisation pour éviter la saturation audio
    sig_norm = signal / np.max(np.abs(signal))
    write(filename, Fe, sig_norm.astype(np.float32))



def play_audio(signal, Fe):
    return Audio(signal, rate=Fe)