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

from src.beamforming.beamforming_signal import Bartlett_plane
from src.signal_process.signal_process import MIScalc
from src.live.acquisition_mu32 import MU32Acquisition
from src.live.audio_buffer import SlidingAudioBuffer
from src.live.camera import LiveCamera
from src.live.projection import CameraBFProjection

from src.live.ui import (
    draw_hud_panel,
    draw_footer,
    draw_status_badge,
    format_on_off,
    handle_key,
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
WIN = "Acoustic Camera - Live"


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
dyn_dB = float(config.dyn_dB)
alpha_scale = float(config.alpha_scale)
alpha_gamma = float(config.alpha_gamma)
use_turbo = False

f_center = float(config.f_start)
show_max = True

t_last = time.perf_counter()
fps = 0.0

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
    "[INFO] Touches: q quit | p HUD | m miroir | "
    "t/y trig | [/] dyn | -/+ alpha | g/G gamma | "
    "j cmap | d max | ,/. freq"
)

# =========================
# MAIN LOOP
# =========================
while True:
    # ---- Caméra
    und = camera.read_undistorted()

    if und is None:
        break

    # ---- Audio : acquérir seulement Th
    block = mu32.read_block(duration=config.Th)
    audio_buffer.push(block)

    # ---- Lecture seuil
    if config.use_trackbar:
        config.level_threshold_dB = (
            cv2.getTrackbarPos("Trig min (dB)", WIN)
            / config.trig_scale
        )

    # ---- Remplissage buffer : pas de BF
    if not audio_buffer.ready:
        disp = und.copy()

        if config.mirror_display:
            disp = cv2.flip(disp, 1)

        if config.show_hud:
            draw_hud_panel(
                disp,
                [
                    (
                        f"Filling audio buffer: "
                        f"{audio_buffer.filled}/{config.win_samp}",
                        (0, 255, 255),
                    ),
                    (
                        f"Tw={config.Tw:.2f}s  Th={config.Th:.2f}s",
                        (230, 230, 230),
                    ),
                    (
                        f"Mirror={format_on_off(config.mirror_display)}",
                        (230, 230, 230),
                    ),
                ],
                width=390,
            )

            draw_footer(
                disp,
                "q quit | p HUD | m mirror | t/y trig | "
                "[ ] dyn | - + alpha | g/G gamma | "
                "j cmap | d max | , . freq",
                config.show_footer,
            )

        cv2.imshow(WIN, disp)

        key = cv2.waitKey(1) & 0xFF

        (
            dyn_dB,
            alpha_scale,
            alpha_gamma,
            use_turbo,
            show_max,
            f_center,
            quit_requested,
        ) = handle_key(
            key,
            config,
            dyn_dB,
            alpha_scale,
            alpha_gamma,
            use_turbo,
            show_max,
            f_center,
        )

        if quit_requested:
            break

        continue

    # ---- MIS + niveau global
    sigbuf = audio_buffer.get_window_channels_first() / config.SMEMS

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

    auto = np.real(np.diag(MISin))
    P_mean = float(np.mean(auto))

    Lp_mean = 10.0 * np.log10(
        (P_mean + config.eps_pressure)
        / (config.p_ref ** 2)
    )

    bf_active = (
        not config.enable_level_trigger
        or Lp_mean >= config.level_threshold_dB
    )

    # Base image : toujours la caméra
    blended = und.copy()

    # ---- BF + overlay seulement si actif
    if bf_active:
        WB_lin = Bartlett_plane(
            f_center=f_center,
            MIS=MISin,
            theta_deg=theta,
            phi_deg=phi,
            mic_positions=geo_positions,
            c=config.c0,
        ).astype(np.float32)

        # Interpolation carte BF -> pixels caméra
        overlay_lin = projection.interpolate_to_pixels(WB_lin)

        # dB relatif : 0 dB au max
        max_lin = float(np.max(overlay_lin) + config.eps_lin)

        overlay_dB = 10.0 * np.log10(
            (overlay_lin + config.eps_lin)
            / max_lin
        )

        vmin = -abs(dyn_dB)
        overlay_dB = np.clip(overlay_dB, vmin, 0.0)

        norm01 = (overlay_dB - vmin) / (0.0 - vmin + 1e-12)
        norm01 = np.clip(norm01, 0.0, 1.0)

        alpha_px = (norm01 ** alpha_gamma) * alpha_scale
        alpha_px = np.clip(alpha_px, 0.0, 1.0)

        # Masque champ caméra utile
        alpha_px[~projection.mask] = 0.0

        heat_u8 = (255.0 * norm01).astype(np.uint8)

        cmap = cv2.COLORMAP_TURBO if use_turbo else cv2.COLORMAP_JET
        heat = cv2.applyColorMap(heat_u8, cmap)

        a3 = np.dstack(
            [alpha_px, alpha_px, alpha_px]
        ).astype(np.float32)

        blended = (
            und.astype(np.float32) * (1.0 - a3)
            + heat.astype(np.float32) * a3
        ).astype(np.uint8)

        # Croix max
        if show_max:
            iy, ix = np.unravel_index(
                int(np.argmax(WB_lin)),
                WB_lin.shape,
            )

            uv = projection.doa_to_pixel(
                float(theta[iy]),
                float(phi[ix]),
            )

            if uv is not None:
                u0, v0p = uv
                Lc = 8

                cv2.line(
                    blended,
                    (u0 - Lc, v0p),
                    (u0 + Lc, v0p),
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

                cv2.line(
                    blended,
                    (u0, v0p - Lc),
                    (u0, v0p + Lc),
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

    # ---- Miroir affichage final : vidéo + beamforming + croix max
    # Important : fait avant le HUD pour garder le texte lisible.
    if config.mirror_display:
        blended = cv2.flip(blended, 1)

    # ---- FPS
    dt = time.perf_counter() - t_last
    t_last = time.perf_counter()

    if dt > 0:
        fps = 0.9 * fps + 0.1 * (1.0 / dt)

    # ---- HUD propre
    state = "ON" if bf_active else "OFF"
    state_col = (0, 220, 0) if bf_active else (0, 0, 255)

    cm_name = "TURBO" if use_turbo else "JET"
    mirror_txt = "MIRROR" if config.mirror_display else "NORMAL"
    max_txt = "MAX" if show_max else "NO MAX"

    if config.show_hud:
        hud_lines = [
            (
                f"BF {state} | f={f_center:.0f} Hz | "
                f"{cm_name} | {mirror_txt}",
                state_col,
            ),
            (
                f"Level={Lp_mean:.1f} dB | "
                f"Trig={config.level_threshold_dB:.1f} dB",
                state_col,
            ),
            (
                f"Tw={config.Tw:.2f}s | "
                f"Th={config.Th:.2f}s | FPS={fps:.1f}",
                (235, 235, 235),
            ),
            (
                f"dyn={dyn_dB:.1f} dB | "
                f"alpha={alpha_scale:.2f} | "
                f"gamma={alpha_gamma:.2f} | {max_txt}",
                (215, 215, 215),
            ),
        ]

        draw_hud_panel(
            blended,
            hud_lines,
            width=505,
        )

        draw_status_badge(
            blended,
            f"BF {state}",
            state_col,
        )

        draw_footer(
            blended,
            "q quit | p HUD | m mirror | t/y trig | "
            "[ ] dyn | - + alpha | g/G gamma | "
            "j cmap | d max | , . freq",
            config.show_footer,
        )

    cv2.imshow(WIN, blended)

    # ---- keys
    key = cv2.waitKey(1) & 0xFF

    (
        dyn_dB,
        alpha_scale,
        alpha_gamma,
        use_turbo,
        show_max,
        f_center,
        quit_requested,
    ) = handle_key(
        key,
        config,
        dyn_dB,
        alpha_scale,
        alpha_gamma,
        use_turbo,
        show_max,
        f_center,
    )

    if quit_requested:
        break


# =========================
# CLEANUP
# =========================
camera.close()
cv2.destroyAllWindows()
mu32.close()