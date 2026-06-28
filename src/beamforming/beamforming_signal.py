# -*- coding: utf-8 -*-
"""
Created on Wed Nov 26 10:50:07 2025

@author: gras
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt

from matplotlib.widgets import Button
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from scipy.signal import spectrogram

from stl import mesh

import os

from src.visu import (
    get_cube_bounds,
    plot_cube_edges,
    add_view_buttons,
    plot_sphere
)
    


def Bartlett_cart(f, MIS, grid_points, mic_positions,
                                   visibility_mask=None,
                                   z_plane=None, R=1.0+0j, c=340.0,
                                   min_mics=3):
    """
    Beamforming Bartlett vectorisé avec visibilité micro/point et plan réfléchi.
    Normalisation simple (sans Option B).

    f              : fréquence (Hz)
    MIS            : matrice de covariance (M,M)
    grid_points    : (N,3) points de la grille d'imagerie
    mic_positions  : (M,3) positions des micros
    visibility_mask: (N,M) booléen, si None tous visibles
    z_plane        : plan réfléchissant (None ou float)
    R              : coefficient de réflexion
    c              : vitesse du son
    min_mics       : nombre minimal de micros visibles
    """

    k = 2 * np.pi * f / c
    M = mic_positions.shape[0]
    N = grid_points.shape[0]

    # ------------------------------------------------------------------
    # Champ direct
    # ------------------------------------------------------------------
    diff = mic_positions[:, None, :] - grid_points[None, :, :]  # (M,N,3)
    r = np.linalg.norm(diff, axis=2)                             # (M,N)
    A_direct = (1.0 / r) * np.exp(-1j * k * r)                  # (M,N)

    # ------------------------------------------------------------------
    # Champ réfléchi (méthode des images)
    # ------------------------------------------------------------------
    if z_plane is not None:
        grid_img = grid_points.copy()
        grid_img[:, 2] = 2.0 * z_plane - grid_points[:, 2]
        diff_img = mic_positions[:, None, :] - grid_img[None, :, :]
        r_img = np.linalg.norm(diff_img, axis=2)
        A_ref = (1.0 / r_img) * np.exp(-1j * k * r_img)
        A = A_direct + R * A_ref
    else:
        A = A_direct

    # ------------------------------------------------------------------
    # Masque de visibilité
    # ------------------------------------------------------------------
    if visibility_mask is not None:
        A *= visibility_mask.T  # (M,N)

    # ------------------------------------------------------------------
    # Bartlett vectorisé avec normalisation simple
    # ------------------------------------------------------------------
    AMA = np.sum(np.conj(A) * (MIS @ A), axis=0)
    norm2 = np.sum(np.abs(A)**2, axis=0)

    S_map = np.zeros(N, dtype=float)
    valid = norm2 > 1e-12
    S_map[valid] = np.real(AMA[valid] / norm2[valid]**2)

    # ------------------------------------------------------------------
    # Seuil minimal de micros visibles
    # ------------------------------------------------------------------
    if visibility_mask is not None:
        Nv = np.sum(visibility_mask, axis=1)
        S_map[Nv < min_mics] = 0.0

    return S_map


from scipy.linalg import eigh



def MUSIC_cart(f_center, MIS, grid_positions, mic_positions,
                                n_sources=1,z_plane=None, R=1.0+0j,
                                c=340.0):
    """
    Beamforming MUSIC avec visibilité micro/point et correction Option B.
    Version robuste : normalisation du steering vector et gestion plan réfléchi.

    f_center        : fréquence d'analyse (Hz)
    MIS             : matrice interspectrale (M,M)
    grid_positions  : (N,3) points test
    mic_positions   : (M,3) positions microphones
    n_sources       : nombre de sources ou masque de modes
    visibility_mask : (N,M) booléen, None => tous visibles
    z_plane         : plan réfléchissant (None ou float)
    R               : coefficient réflexion (si plan)
    c               : vitesse du son (m/s)
    """

    M = mic_positions.shape[0]
    N = grid_positions.shape[0]
    k = 2 * np.pi * f_center / c

    # ------------------------------------------------------------------
    # Décomposition propre de la CSM
    # ------------------------------------------------------------------
 
    eigvals, eigvecs = eigh(MIS)
        
    idx = np.argsort(eigvals)[::-1]
    eigvecs = eigvecs[:, idx]

    # Sous-espace bruit
    En = eigvecs[:, n_sources:]   

    # ------------------------------------------------------------------
    # Steering vector (direct + image)
    # ------------------------------------------------------------------
    diff = mic_positions[:, None, :] - grid_positions[None, :, :]
    r = np.linalg.norm(diff, axis=2)
    A_direct = (1.0 / r) * np.exp(-1j * k * r)

    if z_plane is not None:
        grid_img = grid_positions.copy()
        grid_img[:, 2] = 2.0 * z_plane - grid_positions[:, 2]
        diff_img = mic_positions[:, None, :] - grid_img[None, :, :]
        r_img = np.linalg.norm(diff_img, axis=2)
        A_ref = (1.0 / r_img) * np.exp(-1j * k * r_img)
        A = A_direct + R * A_ref
    else:
        A = A_direct
        
    # ------------------------------------------------------------------
    # Pseudo-spectre MUSIC
    # ------------------------------------------------------------------
    S_map = np.zeros(N, dtype=float)
    for j in range(N):
        a = A[:, j][:, None]
        norm_a = np.linalg.norm(a)
        if norm_a < 1e-12:
            continue
        a /= norm_a  # normalisation par l'énergie visible

        denom = np.linalg.norm(En.conj().T @ a)**2
        if denom > 0:
            S_map[j] = 1.0 / denom
            

    return S_map

def OBF_cart(
    f_center,
    MIS,
    grid_positions,
    mic_positions,
    z_plane=None,
    R=1.0 + 0j,
    c=340.0,
    min_mics=3,
    n_modes=None
):
    """
    Orthogonal Beamforming (OBF) champ proche
    Normalisation ||a||^4 (formulation III).
    Version optimisée.
    """

    M = mic_positions.shape[0]
    N = grid_positions.shape[0]
    k = 2 * np.pi * f_center / c

    # --------------------------------------------------
    # Décomposition spectrale
    # --------------------------------------------------
    eigvals, eigvecs = eigh(MIS)
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    if n_modes is not None:
        eigvals = eigvals[:n_modes]
        eigvecs = eigvecs[:, :n_modes]

    # Sécurité : valeurs propres négatives (CSM non PSD) bornées à 0.
    eigvals = np.clip(eigvals, 0.0, None)

    Nm = eigvals.shape[0]

    # --------------------------------------------------
    # Steering vector
    # --------------------------------------------------
    diff = mic_positions[:, None, :] - grid_positions[None, :, :]
    r = np.linalg.norm(diff, axis=2)
    A = (1.0 / r) * np.exp(-1j * k * r)

    if z_plane is not None:
        grid_img = grid_positions.copy()
        grid_img[:, 2] = 2.0 * z_plane - grid_positions[:, 2]
        diff_img = mic_positions[:, None, :] - grid_img[None, :, :]
        r_img = np.linalg.norm(diff_img, axis=2)
        A += R * (1.0 / r_img) * np.exp(-1j * k * r_img)

    # --------------------------------------------------
    # OBF rapide
    # --------------------------------------------------
    S_modes = np.zeros((Nm, N), dtype=float)

    VH = eigvecs.conj().T   # (Nm, M)

    for j in range(N):
        a = A[:, j]       

        norm2 = np.vdot(a, a).real
        if norm2 < 1e-12:
            continue

        # Projections modales
        y = VH @ a                    # (Nm,)
        S_modes[:, j] = eigvals * (np.abs(y)**2) / norm2**2

    S_map = np.sum(S_modes, axis=0)

    return S_map, S_modes

class PlaneSteering:
    """
    Steering ondes planes pré-calculé et mis en cache par fréquence.

    La géométrie (positions micros) et la grille de directions sont fixes
    sur toute une session : seul ``k0 = 2*pi*f/c`` dépend de la fréquence.
    On pré-calcule donc le produit constant ``B = mic_positions @ dir.T`` une
    seule fois, puis on ne recalcule ``A = exp(1j*k0*B)`` que lorsque
    ``f_center`` change réellement.

    Convention :
    - theta : angle polaire depuis +Z, en degrés
    - phi   : azimut depuis +X dans le plan XY, en degrés
    """

    def __init__(self, theta_deg, phi_deg, mic_positions, c=340.0):
        mic_positions = np.asarray(mic_positions, dtype=np.float64)

        theta = np.deg2rad(theta_deg)
        phi = np.deg2rad(phi_deg)

        self.n_theta = len(theta)
        self.n_phi = len(phi)
        self.c = float(c)

        Theta, Phi = np.meshgrid(theta, phi, indexing="ij")

        ux = np.sin(Theta) * np.cos(Phi)
        uy = np.sin(Theta) * np.sin(Phi)
        uz = np.cos(Theta)

        directions = np.stack(
            (ux, uy, uz),
            axis=-1,
        ).reshape(-1, 3)

        # Partie constante : (M, Ndir)
        self.B = mic_positions @ directions.T

        # Cache de la matrice de steering, indexé par fréquence
        self._f_cached = None
        self._A = None
        self.norm2 = None
        self.valid = None

    def steering(self, f_center):
        """
        Retourne la matrice de steering A (M, Ndir) pour f_center.

        Recalcul de exp(1j*k0*B) uniquement si la fréquence a changé.
        """
        if self._A is None or f_center != self._f_cached:
            k0 = 2.0 * np.pi * f_center / self.c

            self._A = np.exp(1j * k0 * self.B)
            self.norm2 = np.sum(np.abs(self._A) ** 2, axis=0)
            self.valid = self.norm2 > 1e-12
            self._f_cached = f_center

        return self._A


def Bartlett_plane(
    f_center,
    MIS,
    theta_deg,
    phi_deg,
    mic_positions,
    c=340.0,
    steering=None,
):
    """
    Beamforming Bartlett en ondes planes.

    Convention :
    - theta : angle polaire depuis +Z, en degrés
    - phi : azimut depuis +X dans le plan XY, en degrés

    Parameters
    ----------
    f_center : float
        Fréquence d'analyse en Hz.

    MIS : ndarray, shape (M, M)
        Matrice interspectrale.

    theta_deg : ndarray, shape (Ntheta,)
        Grille theta en degrés.

    phi_deg : ndarray, shape (Nphi,)
        Grille phi en degrés.

    mic_positions : ndarray, shape (M, 3)
        Positions microphones.

    c : float
        Vitesse du son en m/s.

    steering : PlaneSteering, optionnel
        Steering pré-calculé/mis en cache. Si None, il est construit à la
        volée (comportement identique, sans cache inter-frames).

    Returns
    -------
    S_map : ndarray, shape (Ntheta, Nphi)
        Carte beamforming Bartlett linéaire.
    """
    if steering is None:
        steering = PlaneSteering(theta_deg, phi_deg, mic_positions, c)

    A = steering.steering(f_center)
    norm2 = steering.norm2
    valid = steering.valid

    AMA = np.sum(
        np.conj(A) * (MIS @ A),
        axis=0,
    )

    S_map = np.zeros_like(AMA.real)
    S_map[valid] = np.real(AMA[valid] / norm2[valid] ** 2)

    return S_map.reshape(steering.n_theta, steering.n_phi)

def OBF_plane(
    f_center,
    MIS,
    theta_deg,
    phi_deg,
    mic_positions,
    c=340.0,
    n_modes=2,
    steering=None,
):
    """
    Orthogonal Beamforming en ondes planes.

    Retourne :
    - S_sum : carte somme des modes retenus, shape (Ntheta, Nphi)
    - S_modes : cartes modales, shape (n_modes, Ntheta, Nphi)

    Convention :
    - theta : angle polaire depuis +Z, en degrés
    - phi : azimut depuis +X dans le plan XY, en degrés

    steering : PlaneSteering, optionnel
        Steering pré-calculé/mis en cache (cf. Bartlett_plane). La matrice A
        ne dépend que de f_center ; seule l'eigendécomposition de la CSM est
        recalculée à chaque appel.
    """
    if steering is None:
        steering = PlaneSteering(theta_deg, phi_deg, mic_positions, c)

    A = steering.steering(f_center)
    norm2 = steering.norm2
    valid = steering.valid

    # --------------------------------------------------
    # Décomposition spectrale de la CSM (dépend des données -> chaque frame)
    # --------------------------------------------------
    eigvals, eigvecs = eigh(MIS)

    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    n_modes = min(n_modes, eigvals.shape[0])

    eigvals = eigvals[:n_modes]
    eigvecs = eigvecs[:, :n_modes]

    # Sécurité : une CSM non semi-définie positive (ex. diag_remove=True, ou
    # bruit numérique) peut produire des valeurs propres négatives, donc des
    # puissances modales négatives. On les borne à 0.
    eigvals = np.clip(eigvals, 0.0, None)

    VH = eigvecs.conj().T  # shape (n_modes, M)

    # Projections modales : shape (n_modes, Ndir)
    Y = VH @ A

    S_modes_flat = np.zeros(
        (n_modes, A.shape[1]),
        dtype=np.float64,
    )

    for imode in range(n_modes):
        S_modes_flat[imode, valid] = (
            eigvals[imode]
            * np.abs(Y[imode, valid]) ** 2
            / norm2[valid] ** 2
        )

    S_modes = S_modes_flat.reshape(n_modes, steering.n_theta, steering.n_phi)
    S_sum = np.sum(S_modes, axis=0)

    return S_sum, S_modes