# -*- coding: utf-8 -*-
"""
Traitements live :
- CSM
- niveau global
- choix algorithme beamforming
"""


import numpy as np

from src.signal_process.signal_process import MIScalc
from src.beamforming.beamforming_signal import (
    Bartlett_plane,
    OBF_plane,
    PlaneSteering,
)


def compute_live_csm(sigbuf, config, f_center):
    """
    Calcule la CSM live à la fréquence f_center.

    Parameters
    ----------
    sigbuf : ndarray, shape (Nch, Nsamp)
        Signaux en Pa.
    """
    config.fmin_bf = f_center - config.delta_f / 2
    config.fmax_bf = f_center + config.delta_f / 2

    f_selected, list_CSM = MIScalc(
        sigbuf,
        config,
        batch_size=32,
        verbose=False,
    )

    idx_f = int(np.argmin(np.abs(f_selected - f_center)))
    MISin = list_CSM[idx_f]

    return MISin, f_selected[idx_f]


def compute_mean_level_db(MISin, config):
    """
    Calcule le niveau moyen autospectral des micros.
    """
    auto = np.real(np.diag(MISin))
    P_mean = float(np.mean(auto))

    Lp_mean = 10.0 * np.log10(
        (P_mean + config.eps_pressure)
        / (config.p_ref ** 2)
    )

    return Lp_mean


def is_beamforming_active(Lp_mean, config):
    """
    Applique le trigger de niveau global.
    """
    return (
        not config.enable_level_trigger
        or Lp_mean >= config.level_threshold_dB
    )


def _get_plane_steering(theta, phi, geo_positions, config, state):
    """
    Récupère (ou crée) le steering ondes planes mis en cache sur state.

    Le steering ne dépend que de la géométrie micros et de la grille
    angulaire, fixes sur toute la session : il est donc construit une seule
    fois puis réutilisé. Si state est None, un steering transitoire est créé
    (pas de cache inter-frames, mais résultat identique).
    """
    steering = getattr(state, "plane_steering", None)

    if steering is None:
        steering = PlaneSteering(theta, phi, geo_positions, c=config.c0)
        if state is not None:
            state.plane_steering = steering

    return steering


def compute_beamforming_map(
    algorithm,
    f_center,
    MISin,
    theta,
    phi,
    geo_positions,
    config,
    state=None,
):
    """
    Calcule la carte BF selon l'algorithme choisi.

    Algorithmes disponibles :
    - BARTLETT_PLANE
    - OBF_PLANE
    """
    algorithm = algorithm.upper()

    # Steering ondes planes : constant sur la session, mis en cache sur state
    # (la matrice A n'est recalculée que lorsque f_center change).
    steering = _get_plane_steering(theta, phi, geo_positions, config, state)

    if algorithm == "BARTLETT_PLANE":
        return Bartlett_plane(
            f_center=f_center,
            MIS=MISin,
            theta_deg=theta,
            phi_deg=phi,
            mic_positions=geo_positions,
            c=config.c0,
            steering=steering,
        ).astype(np.float32)

    if algorithm == "OBF_PLANE":
        n_modes = getattr(state, "obf_n_modes", 2)
        mode_index = getattr(state, "obf_mode_index", 0)

        S_sum, S_modes = OBF_plane(
            f_center=f_center,
            MIS=MISin,
            theta_deg=theta,
            phi_deg=phi,
            mic_positions=geo_positions,
            c=config.c0,
            n_modes=n_modes,
            steering=steering,
        )

        mode_index = int(np.clip(mode_index, 0, S_modes.shape[0] - 1))

        return S_modes[mode_index].astype(np.float32)

    raise ValueError(f"Algorithme live inconnu : {algorithm}")