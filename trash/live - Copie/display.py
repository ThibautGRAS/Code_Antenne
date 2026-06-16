# -*- coding: utf-8 -*-
"""
Fonctions d'affichage pour alléger la boucle live.
"""

import cv2

from src.live.ui import (
    draw_hud_panel,
    draw_footer,
    draw_status_badge,
    format_on_off,
    handle_key,
)


FOOTER_TEXT = (
    "q quit | a algo | 1/2 OBF src | p HUD | m mirror | "
    "t/y trig | [ ] dyn | - + alpha | "
    "g/G gamma | j cmap | d max | , . freq"
)


def render_waiting_buffer_frame(image_bgr, config, audio_buffer):
    """
    Affichage pendant le remplissage du buffer audio.
    """
    blended = image_bgr.copy()

    if config.mirror_display:
        blended = cv2.flip(blended, 1)

    if config.show_hud:
        draw_hud_panel(
            blended,
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
            blended,
            FOOTER_TEXT,
            config.show_footer,
        )

    return blended


def draw_live_hud(
    image_bgr,
    config,
    state,
    bf_active,
    Lp_mean,
):
    """
    Dessine le HUD principal en mode live.    """
    
    bf_txt = "ON" if bf_active else "OFF"
    state_col = (0, 220, 0) if bf_active else (0, 0, 255)

    cm_name = "TURBO" if state.use_turbo else "JET"
    mirror_txt = "MIRROR" if config.mirror_display else "NORMAL"
    max_txt = "MAX" if state.show_max else "NO MAX"

    algo_txt = state.algorithm

    if state.algorithm == "OBF_PLANE":
        algo_txt += f" | source={state.obf_mode_index + 1}/{state.obf_n_modes}"

    hud_lines = [
        (
            f"BF {bf_txt} | algo={algo_txt} | "
            f"f={state.f_center:.0f} Hz | {cm_name} | {mirror_txt}",
            state_col,
        ),
    ]

    draw_hud_panel(
        image_bgr,
        hud_lines,
        width=620,
    )

    draw_status_badge(
        image_bgr,
        f"BF {bf_txt}",
        state_col,
    )

    draw_footer(
        image_bgr,
        FOOTER_TEXT,
        config.show_footer,
    )

    return image_bgr


def process_keyboard(config, state):
    """
    Lit le clavier et met à jour l'état live.
    """
    key = cv2.waitKey(1) & 0xFF

    (
        state.dyn_dB,
        state.alpha_scale,
        state.alpha_gamma,
        state.use_turbo,
        state.show_max,
        state.f_center,
        quit_requested,
    ) = handle_key(
        key,
        config,
        state.dyn_dB,
        state.alpha_scale,
        state.alpha_gamma,
        state.use_turbo,
        state.show_max,
        state.f_center,
    )

    # Changement d'algo
    if key == ord("a"):
        state.next_algorithm()

    # Navigation sources/modes OBF
    elif key == ord("1"):
        state.previous_obf_mode()

    elif key == ord("2"):
        state.next_obf_mode()

    return quit_requested