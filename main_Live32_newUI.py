# -*- coding: utf-8 -*-
"""
Acoustic camera PRO (UNDISTORT + overlay) + SLIDING WINDOW (sans threads)

Étape 1 refactor :
- Config sortie dans data/config_live.py
- Interface sortie dans src/live/ui.py
"""

import os
import math
import time
import signal

import cv2
import numpy as np
import pandas as pd

from data.config_live import Config

from src.live.acquisition_mu32 import MU32Acquisition
from src.live.audio_buffer import SlidingAudioBuffer
from src.live.camera import LiveCamera
from src.live.projection import CameraBFProjection
from src.live.live_state import LiveState
from src.live.overlay import AcousticOverlayRenderer
from src.live.recorder import LiveRecorder

from src.live.live_processing import (
    compute_live_csm,
    compute_mean_level_db,
    is_beamforming_active,
    compute_beamforming_map,)

from src.live.display import (
    render_waiting_buffer_frame,
    compose_live_dashboard,
    process_keyboard_from_key,
    get_logo,
)

from src.live.setup import (
    load_camera_calibration,
    compute_theta_grid_from_camera,
    load_microphone_geometry,
    init_opencv_window,
)


# =========================
# CONFIG
# =========================
config = Config()
WIN = "CAMERA ACOUSTIQUE LIVE"


# =========================
# SETUP DONNEES
# =========================
K, dist = load_camera_calibration(config)

w = int(config.cam_w)
h = int(config.cam_h)

theta, theta_max = compute_theta_grid_from_camera(config, K)
phi = config.phi

geo_positions = load_microphone_geometry(config)


# =========================
# MU32 INIT
# =========================
mu32 = MU32Acquisition(
    sampling_rate=config.Fe,
    verbose=False,
)
mu32.start()


def signal_handler(sig, frame):
    mu32.close()


signal.signal(signal.SIGINT, signal_handler)


# =========================
# CAMERA INIT
# =========================
camera = LiveCamera(config, K, dist)
camera.start()

newK = camera.newK


# =========================
# PROJECTION
# =========================
projection = CameraBFProjection(
    config=config,
    newK=newK,
    w=w,
    h=h,
    theta=theta,
    phi=phi,
    theta_max=theta_max,
)


# =========================
# BUFFER
# =========================
audio_buffer = SlidingAudioBuffer(config.win_samp)


# =========================
# UI INIT
# =========================
init_opencv_window(WIN, config)


# =========================
# LOOP STATE
# =========================
state = LiveState(config)
state.recorder = LiveRecorder()

overlay_renderer = AcousticOverlayRenderer(
    config=config,
    projection=projection,
    theta=theta,
    phi=phi,
)

logo_rgba = get_logo(config)

print(
    f"[INFO] theta_max ≈ {theta_max:.2f} deg | "
    f"D={config.proj_distance_m:.2f} m | offset={config.cam_offset}"
)

print(
    f"[INFO] Sliding window: Tw={config.Tw:.2f}s "
    f"({config.win_samp} samp) | "
    f"Th={config.Th:.2f}s ({config.hop_samp} samp)"
)

print(
    "[INFO] Touches: q quit | r rec | p HUD | m miroir | "
    "t/y trig | w/x dyn | -/+ alpha | g/G gamma | "
    "j cmap | d max | ,/; freq"
)

# =========================
# MAIN LOOP
# =========================
while True:
    # ------------------------------------------------------------
    # 1) Caméra
    # ------------------------------------------------------------
    und = camera.read_undistorted()

    if und is None:
        break

    # ------------------------------------------------------------
    # 2) Acquisition audio + buffer glissant
    # ------------------------------------------------------------
    block = mu32.read_block(duration=config.Th)
    audio_buffer.push(block)

    # ------------------------------------------------------------
    # 3) Lecture paramètres interface
    # ------------------------------------------------------------
    if config.use_trackbar:
        config.level_threshold_dB = (
            cv2.getTrackbarPos("Trig min (dB)", WIN)
            / config.trig_scale
        )

    # ------------------------------------------------------------
    # 4) Buffer pas encore rempli
    # ------------------------------------------------------------
    if not audio_buffer.ready:
        blended = render_waiting_buffer_frame(
            image_bgr=und,
            config=config,
            audio_buffer=audio_buffer,
            state=state,
            logo_rgba=logo_rgba,
        )

        display_scale = float(getattr(config, "ui_display_scale", 1.0))

        if abs(display_scale - 1.0) > 1e-6:
            blended_show = cv2.resize(
                blended,
                None,
                fx=display_scale,
                fy=display_scale,
                interpolation=cv2.INTER_CUBIC,
            )
        else:
            blended_show = blended

        cv2.imshow(WIN, blended_show)

        state.recorder.write(blended_show)

        if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
            print("[INFO] Fenetre fermee par l'utilisateur")
            break

        key = cv2.waitKey(1) & 0xFF

        if key == ord("r"):
            rec_fps = float(getattr(config, "record_fps", 0.0))

            if rec_fps <= 0.0:
                rec_fps = max(1.0, min(30.0, float(getattr(state, "fps", 10.0))))

            state.recorder.toggle(dashboard_show, config, fps=rec_fps)

        elif process_keyboard_from_key(key, config, state):
            break

        continue

    # ------------------------------------------------------------
    # 5) CSM + niveau global
    # ------------------------------------------------------------
    sigbuf = audio_buffer.get_window_channels_first() / config.SMEMS

    MISin, f_real = compute_live_csm(
        sigbuf=sigbuf,
        config=config,
        f_center=state.f_center,
    )

    Lp_mean = compute_mean_level_db(
        MISin=MISin,
        config=config,
    )

    bf_active = is_beamforming_active(
        Lp_mean=Lp_mean,
        config=config,
    )

    # ------------------------------------------------------------
    # 6) Beamforming + overlay
    # ------------------------------------------------------------
    blended = und.copy()

    if bf_active:
        WB_lin = compute_beamforming_map(
            algorithm=state.algorithm,
            f_center=state.f_center,
            MISin=MISin,
            theta=theta,
            phi=phi,
            geo_positions=geo_positions,
            config=config,
            state=state,
        )

        # Valeurs dB de la carte BF pour la barre du bas
        map_max_lin = float(np.max(WB_lin) + config.eps_lin)

        state.last_map_max_db = 10.0 * np.log10(
            map_max_lin / (config.p_ref ** 2)
        )

        state.last_map_min_db = state.last_map_max_db - state.dyn_dB

        blended = overlay_renderer.render(
            image_bgr=und,
            WB_lin=WB_lin,
            dyn_dB=state.dyn_dB,
            alpha_scale=state.alpha_scale,
            alpha_gamma=state.alpha_gamma,
            use_turbo=state.use_turbo,
            show_max=state.show_max,
        )

    else:
        state.last_map_max_db = None
        state.last_map_min_db = None

    # ------------------------------------------------------------
    # 7) Affichage final
    # ------------------------------------------------------------
    if config.mirror_display:
        blended = cv2.flip(blended, 1)

    state.update_fps()

    dashboard = compose_live_dashboard(
        camera_frame=blended,
        config=config,
        state=state,
        bf_active=bf_active,
        Lp_mean=Lp_mean,
        f_real=f_real,
        logo_rgba=logo_rgba,
    )

    display_scale = float(getattr(config, "ui_display_scale", 1.0))

    if abs(display_scale - 1.0) > 1e-6:
        dashboard_show = cv2.resize(
            dashboard,
            None,
            fx=display_scale,
            fy=display_scale,
            interpolation=cv2.INTER_CUBIC,
        )
    else:
        dashboard_show = dashboard

    # Affiche vraiment l'image redimensionnée
    cv2.imshow(WIN, dashboard_show)

    # Enregistre exactement l'image affichée si l'enregistrement est actif
    state.recorder.write(dashboard_show)

    # Croix de fermeture fenêtre = quit
    if cv2.getWindowProperty(WIN, cv2.WND_PROP_VISIBLE) < 1:
        print("[INFO] Fenetre fermee par l'utilisateur")
        break

    key = cv2.waitKey(1) & 0xFF

    if key == ord("r"):
        rec_fps = float(getattr(config, "record_fps", 0.0))

        if rec_fps <= 0.0:
            rec_fps = max(1.0, min(30.0, float(getattr(state, "fps", 10.0))))

        state.recorder.toggle(dashboard_show, config, fps=rec_fps)

    elif process_keyboard_from_key(key, config, state):
        break


# =========================
# CLEANUP
# =========================
state.recorder.close()
camera.close()
cv2.destroyAllWindows()
mu32.close()