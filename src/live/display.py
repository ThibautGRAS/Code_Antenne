# -*- coding: utf-8 -*-
"""
Composition de l'interface live dashboard.
"""

import cv2
import numpy as np

from src.live.ui import (
    handle_key,
    draw_header_bar,
    draw_panel_box,
    draw_key_value_rows,
    draw_bottom_level_bar,
    draw_shortcuts_box,
    load_rgba_image,
    bgr,draw_recording_indicator,
)


SHORTCUTS = [
    ("q", "Quitter"),
    ("r", "Rec on/off"),
    ("c", "Camera seule"),
    ("p", "HUD on/off"),
    ("a", "Changer algo"),
    ("1/2", "Source OBF"),
    (",/;", "Frequence"),
    ("w/x", "Dynamique"),
    ("+/-", "Transparence"),
    ("t/y", "Trigger"),
    ("d", "croix max"),
    ("j", "Colormap"),
    ("m", "Miroir"),
]

def process_keyboard(config, state):
    key = cv2.waitKey(1) & 0xFF
    return process_keyboard_from_key(key, config, state)

def process_keyboard_from_key(key, config, state):
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

    if key == ord("a"):
        state.next_algorithm()

    elif key == ord("1"):
        state.previous_obf_mode()

    elif key == ord("2"):
        state.next_obf_mode()

    elif key == ord("c"):
        state.toggle_camera_only()

    return quit_requested

def get_logo(config):
    """
    Charge le logo CETIM si disponible.
    """
    if not getattr(config, "show_logo_cetim", False):
        print("[INFO] Logo CETIM desactive : show_logo_cetim=False")
        return None

    logo_path = getattr(config, "cetim_logo_path", None)

    print("[DEBUG] chemin logo CETIM =", logo_path)

    if logo_path is None:
        print("[WARNING] config.cetim_logo_path absent")
        return None

    logo = load_rgba_image(logo_path)

    if logo is None:
        print("[WARNING] Logo CETIM non trouve ou illisible :", logo_path)
    else:
        print("[INFO] Logo CETIM charge :", logo.shape)

    return logo


def render_waiting_buffer_frame(
    image_bgr,
    config,
    audio_buffer,
    state=None,
    logo_rgba=None,
):
    if state is not None and getattr(state, "camera_only", False):
        return compose_camera_only_frame(
            camera_frame=image_bgr,
            config=config,
            state=state,
        )

    return compose_live_dashboard(
        camera_frame=image_bgr,
        config=config,
        state=state,
        bf_active=False,
        Lp_mean=0.0,
        f_real=None,
        logo_rgba=logo_rgba,
        waiting_text=f"Buffer {audio_buffer.filled}/{config.win_samp}",
    )


def compose_camera_only_frame(
    camera_frame,
    config,
    state,
):
    """
    Mode camera seule : image camera + beamforming uniquement.
    """
    frame = camera_frame.copy()

    if getattr(config, "show_shortcuts_overlay", True) and getattr(config, "show_hud", True):
        draw_shortcuts_box(
            frame,
            x=14,
            y=14,
            shortcuts=SHORTCUTS,
            title="Raccourcis",
            accent_color=(0, 220, 255),
            text_color=(245, 245, 245),
            alpha=0.35,
        )

    return frame


def compose_live_dashboard(
    camera_frame,
    config,
    state,
    bf_active,
    Lp_mean,
    f_real=None,
    logo_rgba=None,
    waiting_text=None,
):
    """
    Compose l'image complete du dashboard.
    """

    if state is not None and getattr(state, "camera_only", False):
        return compose_camera_only_frame(
            camera_frame=camera_frame,
            config=config,
            state=state,
        )

    cam_h, cam_w = camera_frame.shape[:2]

    header_h = int(getattr(config, "ui_header_h", 44))
    right_w = int(getattr(config, "ui_right_panel_w", 300))
    bottom_h = int(getattr(config, "ui_bottom_bar_h", 62))

    total_w = cam_w + right_w
    total_h = header_h + cam_h + bottom_h

    bg_color = bgr(getattr(config, "ui_bg_color", [5, 28, 55]))
    header_color = bgr(getattr(config, "ui_header_color", [0, 48, 85]))
    panel_color = bgr(getattr(config, "ui_panel_color", [8, 42, 78]))
    border_color = bgr(getattr(config, "ui_panel_border_color", [80, 150, 200]))
    text_color = bgr(getattr(config, "ui_text_color", [235, 240, 245]))
    accent_color = bgr(getattr(config, "ui_accent_color", [70, 190, 230]))
    good_color = bgr(getattr(config, "ui_good_color", [120, 220, 90]))
    alert_color = bgr(getattr(config, "ui_alert_color", [255, 70, 70]))

    frame = np.full(
        (total_h, total_w, 3),
        bg_color,
        dtype=np.uint8,
    )

    # ------------------------------------------------------------
    # Header
    # ------------------------------------------------------------
    draw_header_bar(
        frame,
        title="CAMERA ACOUSTIQUE LIVE",
        logo_rgba=logo_rgba,
        header_h=header_h,
        bg_color=header_color,
        text_color=text_color,
        accent_color=accent_color,
    )

    # ------------------------------------------------------------
    # Image camera
    # ------------------------------------------------------------
    cam_x = 0
    cam_y = header_h

    frame[cam_y:cam_y + cam_h, cam_x:cam_x + cam_w] = camera_frame

    cv2.rectangle(
        frame,
        (cam_x, cam_y),
        (cam_x + cam_w - 1, cam_y + cam_h - 1),
        border_color,
        1,
        cv2.LINE_AA,
    )

    # ------------------------------------------------------------
    # Panneau droit informations
    # ------------------------------------------------------------
    panel_x = cam_w + 8
    panel_y = header_h + 8
    panel_w = right_w - 16
    panel_h = cam_h - 16

    draw_info_panel(
        frame,
        x=panel_x,
        y=panel_y,
        w=panel_w,
        h=panel_h,
        config=config,
        state=state,
        bf_active=bf_active,
        Lp_mean=Lp_mean,
        f_real=f_real,
        panel_color=panel_color,
        border_color=border_color,
        text_color=text_color,
        good_color=good_color,
        alert_color=alert_color,
        waiting_text=waiting_text,
    )

    # ------------------------------------------------------------
    # Barre bas
    # ------------------------------------------------------------
    bottom_y = header_h + cam_h

    dyn_dB = state.dyn_dB if state is not None else config.dyn_dB

    draw_bottom_level_bar(
        frame,
        x=0,
        y=header_h + cam_h,
        w=total_w,
        h=bottom_h,
        level_db=Lp_mean,
        trigger_db=config.level_threshold_dB,
        bf_active=bf_active,
        dyn_dB=state.dyn_dB,
        colorbar_width_ratio=float(getattr(config, "ui_colorbar_width_ratio", 0.52)),
        map_max_db=getattr(state, "last_map_max_db", None),
    )

    # ------------------------------------------------------------
    # HUD raccourcis transparent
    # ------------------------------------------------------------
    if getattr(config, "show_shortcuts_overlay", True) and getattr(config, "show_hud", True):
        draw_shortcuts_box(
            frame,
            x=14,
            y=header_h + 14,
            shortcuts=SHORTCUTS,
            title="Raccourcis",
            accent_color=accent_color,
            text_color=text_color,
            alpha=0.38,
        )

    recorder = getattr(state, "recorder", None)

    draw_recording_indicator(
        frame,
        is_recording=(recorder is not None and recorder.is_recording),
        x=total_w - 118,
        y=8,
    )

    return frame


def draw_info_panel(
    frame,
    x,
    y,
    w,
    h,
    config,
    state,
    bf_active,
    Lp_mean,
    f_real,
    panel_color,
    border_color,
    text_color,
    good_color,
    alert_color,
    waiting_text=None,
):
    """
    Panneau informations.
    """
    draw_panel_box(
        frame,
        x=x,
        y=y,
        w=w,
        h=h,
        title="Informations",
        panel_color=panel_color,
        border_color=border_color,
        text_color=text_color,
        radius=10,
    )

    if state is None:
        f_txt = f"{config.f_start:.0f} Hz"
        algo_txt = "-"
        source_txt = ""
        mirror_txt = "OFF"
        dyn_txt = f"{config.dyn_dB:.1f} dB"
    else:
        # Demande utilisateur : seulement 2000 Hz, pas 2000 Hz (2000)
        f_txt = f"{state.f_center:.0f} Hz"

        if state.algorithm == "BARTLETT_PLANE":
            algo_txt = "Bartlett plane"
            source_txt = ""
        elif state.algorithm == "OBF_PLANE":
            algo_txt = "OBF"
            source_txt = f"{state.obf_mode_index + 1}/{state.obf_n_modes}"
        else:
            algo_txt = state.algorithm
            source_txt = ""

        mirror_txt = "ON" if config.mirror_display else "OFF"
        dyn_txt = f"{state.dyn_dB:.1f} dB"

    if waiting_text is not None:
        level_txt = waiting_text
        level_color = (0, 255, 255)
    else:
        level_txt = f"{Lp_mean:.1f} dB"
        level_color = alert_color if Lp_mean >= config.level_threshold_dB else good_color

    rows = [
        ("Frequence (f)", f_txt, good_color),
        ("Tw (fenetre)", f"{config.Tw:.2f} s".replace(".", ","), good_color),
        ("Th (mise a jour)", f"{config.Th:.2f} s".replace(".", ","), good_color),
        ("Declenchement", f"{config.level_threshold_dB:.1f} dB".replace(".", ","), alert_color),
        ("Dynamique", dyn_txt.replace(".", ","), good_color),
        ("Algo utilise", algo_txt, text_color),
        ("Source", source_txt, text_color),
        ("Miroir image", mirror_txt, text_color),
    ]

    draw_key_value_rows(
        frame,
        rows=rows,
        x=x + 14,
        y=y + 48,
        w=w - 28,
        row_h=24,
        key_color=text_color,
        value_color=good_color,
        font_scale=0.40,
    )

    return frame