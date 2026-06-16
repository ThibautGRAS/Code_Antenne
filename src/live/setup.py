# -*- coding: utf-8 -*-
"""
Fonctions de préparation du live :
- calibration caméra
- grille angulaire
- géométrie microphones
- fenêtre OpenCV
"""

import math
import cv2
import numpy as np
import pandas as pd


def load_camera_calibration(config):
    """
    Charge la calibration caméra OpenCV.

    Returns
    -------
    K : ndarray, shape (3, 3)
    dist : ndarray
    """
    if not config.calib_file.exists():
        raise FileNotFoundError(
            f"Calibration caméra introuvable : {config.calib_file}"
        )

    cal = np.load(config.calib_file, allow_pickle=True)

    K = cal["camera_matrix"].astype(np.float64)
    dist = cal["dist_coeffs"].astype(np.float64).reshape(-1, 1)

    return K, dist


def compute_theta_grid_from_camera(config, K):
    """
    Calcule theta_max et la grille theta tan-uniforme
    à partir de la focale caméra.
    """
    w = int(config.cam_w)
    h = int(config.cam_h)

    fx = K[0, 0]
    fy = K[1, 1]

    alpha = math.atan(w / (2.0 * fx))
    beta = math.atan(h / (2.0 * fy))

    theta_max = math.degrees(
        math.atan(
            math.sqrt(
                math.tan(alpha) ** 2
                + math.tan(beta) ** 2
            )
        )
    )

    theta_max = min(
        theta_max + config.theta_margin_deg,
        config.theta_max_limit_deg,
    )

    theta_max_rad = np.deg2rad(theta_max)
    t_max = np.tan(theta_max_rad)

    t_vals = np.linspace(
        0.0,
        t_max,
        config.Ltheta,
    )

    theta = np.rad2deg(np.arctan(t_vals))

    config.theta = theta
    config.theta_max = theta_max

    return theta, theta_max


def load_microphone_geometry(config):
    """
    Charge la géométrie microphones depuis le CSV.
    """
    if not config.geo_file.exists():
        raise FileNotFoundError(
            f"Fichier géométrie microphones introuvable : {config.geo_file}"
        )

    geo_df = pd.read_csv(config.geo_file, sep=";")
    geo_positions = geo_df[["X", "Y", "Z"]].values.astype(np.float64)

    return geo_positions


def init_opencv_window(window_name, config):
    scale = float(getattr(config, "ui_display_scale", 1.0))

    w = int((int(config.cam_w) + int(getattr(config, "ui_right_panel_w", 300))) * scale)
    h = int((
        int(getattr(config, "ui_header_h", 56))
        + int(config.cam_h)
        + int(getattr(config, "ui_bottom_bar_h", 62))
    ) * scale)

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, w, h)