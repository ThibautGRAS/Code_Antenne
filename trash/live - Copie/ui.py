# -*- coding: utf-8 -*-
"""
Fonctions d'interface OpenCV pour l'application live.

Contient :
- HUD semi-transparent
- footer clavier
- badge statut
- gestion des touches clavier
"""


import cv2


def draw_alpha_rect(img, pt1, pt2, color=(0, 0, 0), alpha=0.45):
    """Dessine un rectangle semi-transparent directement dans img."""
    h_img, w_img = img.shape[:2]
    x1, y1 = pt1
    x2, y2 = pt2

    x1 = max(0, min(w_img - 1, int(x1)))
    x2 = max(0, min(w_img - 1, int(x2)))
    y1 = max(0, min(h_img - 1, int(y1)))
    y2 = max(0, min(h_img - 1, int(y2)))

    if x2 <= x1 or y2 <= y1:
        return img

    overlay = img.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    img[:] = cv2.addWeighted(overlay, alpha, img, 1.0 - alpha, 0)
    return img


def draw_hud_panel(img, lines, x=10, y=10, width=None, font_scale=0.48):
    """
    Affiche un panneau compact semi-transparent.

    Parameters
    ----------
    img : ndarray
        Image OpenCV BGR.
    lines : list[tuple[str, tuple]]
        Liste de lignes : [(texte, couleur_BGR), ...]
    """
    h_img, w_img = img.shape[:2]
    pad = 9
    line_h = 21

    if width is None:
        width = min(w_img - 2 * x, 510)

    height = pad * 2 + line_h * len(lines)

    draw_alpha_rect(
        img,
        (x, y),
        (x + width, y + height),
        color=(0, 0, 0),
        alpha=0.48,
    )

    yy = y + pad + 15

    for text, color in lines:
        cv2.putText(
            img,
            text,
            (x + pad, yy),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            1,
            cv2.LINE_AA,
        )
        yy += line_h

    return img


def draw_footer(img, text, show=True):
    """Affiche une ligne d'aide discrète en bas."""
    if not show:
        return img

    h_img, w_img = img.shape[:2]
    bar_h = 30

    draw_alpha_rect(
        img,
        (0, h_img - bar_h),
        (w_img, h_img),
        color=(0, 0, 0),
        alpha=0.42,
    )

    cv2.putText(
        img,
        text,
        (10, h_img - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (230, 230, 230),
        1,
        cv2.LINE_AA,
    )

    return img


def draw_status_badge(img, text, color, x=None, y=10):
    """Affiche un petit badge en haut à droite."""
    h_img, w_img = img.shape[:2]

    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.52
    th = 1
    pad_x, pad_y = 8, 6

    (tw, th_text), _ = cv2.getTextSize(text, font, fs, th)

    bw = tw + 2 * pad_x
    bh = th_text + 2 * pad_y

    if x is None:
        x = w_img - bw - 10

    draw_alpha_rect(
        img,
        (x, y),
        (x + bw, y + bh),
        color=(0, 0, 0),
        alpha=0.50,
    )

    cv2.putText(
        img,
        text,
        (x + pad_x, y + pad_y + th_text),
        font,
        fs,
        color,
        th,
        cv2.LINE_AA,
    )

    return img


def format_on_off(value):
    """Retourne ON/OFF pour affichage."""
    return "ON" if value else "OFF"


def handle_key(
    key,
    config,
    dyn_dB,
    alpha_scale,
    alpha_gamma,
    use_turbo,
    show_max,
    f_center,
):
    """
    Gestion centralisée des touches clavier.

    Retourne
    --------
    dyn_dB, alpha_scale, alpha_gamma, use_turbo, show_max, f_center, quit_requested
    """
    quit_requested = False

    if key == ord("q"):
        quit_requested = True

    elif key == ord("p"):
        config.show_hud = not config.show_hud
        print(f"[INFO] show_hud={config.show_hud}")

    elif key == ord("m"):
        config.mirror_display = not config.mirror_display
        print(f"[INFO] mirror_display={config.mirror_display}")

    elif key == ord("t"):
        config.level_threshold_dB = max(
            0.0,
            config.level_threshold_dB - 1.0,
        )
        print(f"[INFO] Trig={config.level_threshold_dB:.1f} dB")

    elif key == ord("y"):
        config.level_threshold_dB = min(
            config.trig_max_dB,
            config.level_threshold_dB + 1.0,
        )
        print(f"[INFO] Trig={config.level_threshold_dB:.1f} dB")

    elif key == ord("["):
        dyn_dB = max(1.0, dyn_dB - 1.0)

    elif key == ord("]"):
        dyn_dB = min(60.0, dyn_dB + 1.0)

    elif key == ord("-"):
        alpha_scale = max(0.0, alpha_scale - 0.05)

    elif key == ord("+") or key == ord("="):
        alpha_scale = min(1.0, alpha_scale + 0.05)

    elif key == ord("g"):
        alpha_gamma = max(0.2, alpha_gamma - 0.05)

    elif key == ord("G"):
        alpha_gamma = min(3.0, alpha_gamma + 0.05)

    elif key == ord("j"):
        use_turbo = not use_turbo

    elif key == ord("d"):
        show_max = not show_max

    elif key == ord("<") or key == ord(","):
        f_center = max(config.f_min, f_center - config.f_step)

    elif key == ord(">") or key == ord("."):
        f_center = min(config.f_max, f_center + config.f_step)

    return (
        dyn_dB,
        alpha_scale,
        alpha_gamma,
        use_turbo,
        show_max,
        f_center,
        quit_requested,
    )