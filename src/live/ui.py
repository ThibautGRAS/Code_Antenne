# -*- coding: utf-8 -*-
"""
Fonctions d'interface OpenCV pour l'application live.

Ce fichier regroupe :
- le rendu haute qualite des textes avec Pillow ;
- les primitives graphiques OpenCV : panneaux, rectangles arrondis, transparence ;
- les elements du dashboard : header, panneau informations, barre du bas ;
- les anciens elements HUD/footer utiles en mode camera ;
- la gestion centralisee des touches clavier.

Convention couleur :
- les couleurs passees aux fonctions OpenCV sont en BGR ;
- les couleurs venant du YAML sont en RGB et doivent passer par bgr().
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ============================================================
# 1) RENDU TEXTE HAUTE QUALITE AVEC PILLOW
# ============================================================

_FONT_CACHE = {}


# ------------------------------------------------------------
# Charge une police moderne avec cache.
# ------------------------------------------------------------
def get_ui_font(size=16, bold=False):
    """
    Charge une police moderne Windows.
    Utilise Segoe UI si disponible, sinon Arial, sinon police par defaut.
    """
    key = (int(size), bool(bold))

    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    if bold:
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
        ]
    else:
        candidates = [
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]

    font = None

    for path in candidates:
        if Path(path).exists():
            font = ImageFont.truetype(path, size=int(size))
            break

    if font is None:
        font = ImageFont.load_default()

    _FONT_CACHE[key] = font
    return font


# ------------------------------------------------------------
# Dessine un texte propre sur une image OpenCV BGR.
# ------------------------------------------------------------
def draw_text_pil(
    img_bgr,
    text,
    x,
    y,
    color=(235, 240, 245),
    size=16,
    bold=False,
    anchor="la",
):
    """
    Dessine du texte avec Pillow dans une image OpenCV.

    Parameters
    ----------
    img_bgr : ndarray
        Image OpenCV en BGR.
    text : str
        Texte a afficher.
    x, y : int
        Position du texte.
    color : tuple
        Couleur BGR.
    size : int
        Taille de police.
    bold : bool
        Police grasse ou non.
    anchor : str
        Ancrage Pillow. Exemples utiles :
        - "la" : left / ascender ;
        - "lm" : left / middle ;
        - "mm" : middle / middle.
    """
    if text is None:
        return img_bgr

    text = str(text)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img_rgb)
    draw = ImageDraw.Draw(pil_img)

    font = get_ui_font(size=size, bold=bold)

    b, g, r = color
    rgb = (int(r), int(g), int(b))

    draw.text(
        (int(x), int(y)),
        text,
        font=font,
        fill=rgb,
        anchor=anchor,
    )

    img_bgr[:] = cv2.cvtColor(np.asarray(pil_img), cv2.COLOR_RGB2BGR)

    return img_bgr


# ------------------------------------------------------------
# Mesure la taille d'un texte Pillow.
# ------------------------------------------------------------
def text_size_pil(text, size=16, bold=False):
    """
    Retourne la taille en pixels d'un texte rendu avec Pillow.
    """
    font = get_ui_font(size=size, bold=bold)
    dummy = Image.new("RGB", (10, 10))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), str(text), font=font)

    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    return w, h


# ============================================================
# 2) COULEURS ET PRIMITIVES GRAPHIQUES DE BASE
# ============================================================

# ------------------------------------------------------------
# Convertit une couleur RGB YAML vers BGR OpenCV.
# ------------------------------------------------------------
def bgr(color):
    """
    Convertit une couleur RGB venant du YAML en BGR pour OpenCV.

    YAML :
        [R, G, B]

    OpenCV :
        (B, G, R)
    """
    if color is None:
        return (0, 0, 0)

    r, g, b = color
    return (int(b), int(g), int(r))


# ------------------------------------------------------------
# Dessine un rectangle semi-transparent dans l'image.
# ------------------------------------------------------------
def draw_alpha_rect(img, pt1, pt2, color=(0, 0, 0), alpha=0.45):
    """
    Dessine un rectangle semi-transparent directement dans img.
    """
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


# ------------------------------------------------------------
# Dessine un rectangle a coins arrondis.
# ------------------------------------------------------------
def draw_rounded_rect(
    img,
    pt1,
    pt2,
    color=(20, 45, 75),
    radius=10,
    thickness=-1,
    line_type=cv2.LINE_AA,
):
    """
    Dessine un rectangle a coins arrondis.
    OpenCV ne le fait pas nativement, donc on combine rectangles + cercles.
    """
    x1, y1 = pt1
    x2, y2 = pt2

    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    radius = int(radius)

    if x2 <= x1 or y2 <= y1:
        return img

    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))

    if thickness < 0:
        # Remplissage du centre et des bandes.
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y2), color, -1, line_type)
        cv2.rectangle(img, (x1, y1 + radius), (x2, y2 - radius), color, -1, line_type)

        # Coins arrondis.
        cv2.circle(img, (x1 + radius, y1 + radius), radius, color, -1, line_type)
        cv2.circle(img, (x2 - radius, y1 + radius), radius, color, -1, line_type)
        cv2.circle(img, (x1 + radius, y2 - radius), radius, color, -1, line_type)
        cv2.circle(img, (x2 - radius, y2 - radius), radius, color, -1, line_type)

    else:
        # Contour approximatif.
        cv2.line(img, (x1 + radius, y1), (x2 - radius, y1), color, thickness, line_type)
        cv2.line(img, (x1 + radius, y2), (x2 - radius, y2), color, thickness, line_type)
        cv2.line(img, (x1, y1 + radius), (x1, y2 - radius), color, thickness, line_type)
        cv2.line(img, (x2, y1 + radius), (x2, y2 - radius), color, thickness, line_type)

        cv2.ellipse(img, (x1 + radius, y1 + radius), (radius, radius), 180, 0, 90, color, thickness, line_type)
        cv2.ellipse(img, (x2 - radius, y1 + radius), (radius, radius), 270, 0, 90, color, thickness, line_type)
        cv2.ellipse(img, (x2 - radius, y2 - radius), (radius, radius), 0, 0, 90, color, thickness, line_type)
        cv2.ellipse(img, (x1 + radius, y2 - radius), (radius, radius), 90, 0, 90, color, thickness, line_type)

    return img


# ============================================================
# 3) IMAGES RGBA : LOGO ET OVERLAYS
# ============================================================

# ------------------------------------------------------------
# Charge une image avec canal alpha.
# ------------------------------------------------------------
def load_rgba_image(path):
    """
    Charge une image RGBA.
    Retourne None si le fichier est absent ou illisible.
    """
    if path is None:
        return None

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)

    if img is None:
        return None

    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)

    elif img.shape[2] == 3:
        alpha = np.full(img.shape[:2], 255, dtype=np.uint8)
        img = np.dstack([img, alpha])

    return img


# ------------------------------------------------------------
# Superpose une image RGBA sur une image BGR.
# ------------------------------------------------------------
def overlay_rgba_image(
    background_bgr,
    overlay_rgba,
    x,
    y,
    alpha_scale=1.0,
    target_w=None,
    target_h=None,
):
    """
    Superpose une image RGBA sur une image BGR.
    Le redimensionnement conserve le ratio si un seul de target_w/target_h est donne.
    """
    if overlay_rgba is None:
        return background_bgr

    ov = overlay_rgba.copy()

    if target_w is not None or target_h is not None:
        h0, w0 = ov.shape[:2]

        if target_w is None:
            scale = float(target_h) / float(h0)
            target_w = int(w0 * scale)

        if target_h is None:
            scale = float(target_w) / float(w0)
            target_h = int(h0 * scale)

        ov = cv2.resize(
            ov,
            (int(target_w), int(target_h)),
            interpolation=cv2.INTER_AREA,
        )

    h, w = ov.shape[:2]
    H, W = background_bgr.shape[:2]

    x = int(x)
    y = int(y)

    if x >= W or y >= H:
        return background_bgr

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(W, x + w)
    y2 = min(H, y + h)

    if x2 <= x1 or y2 <= y1:
        return background_bgr

    ox1 = x1 - x
    oy1 = y1 - y
    ox2 = ox1 + (x2 - x1)
    oy2 = oy1 + (y2 - y1)

    roi = background_bgr[y1:y2, x1:x2]
    ov_crop = ov[oy1:oy2, ox1:ox2]

    if ov_crop.shape[2] == 4:
        rgb = ov_crop[:, :, :3].astype(np.float32)
        alpha = ov_crop[:, :, 3].astype(np.float32) / 255.0
        alpha = np.clip(alpha * alpha_scale, 0.0, 1.0)
        alpha = alpha[:, :, None]
    else:
        rgb = ov_crop.astype(np.float32)
        alpha = np.ones_like(rgb[:, :, :1], dtype=np.float32) * alpha_scale

    blended = roi.astype(np.float32) * (1.0 - alpha) + rgb * alpha
    background_bgr[y1:y2, x1:x2] = blended.astype(np.uint8)

    return background_bgr


# ------------------------------------------------------------
# Centre un logo RGBA dans une capsule ou une zone donnee.
# ------------------------------------------------------------
def overlay_rgba_fit_center(
    background_bgr,
    overlay_rgba,
    box_x,
    box_y,
    box_w,
    box_h,
    margin_x=10,
    margin_y=6,
    alpha_scale=1.0,
):
    """
    Centre une image RGBA dans une boite, en conservant le ratio.
    Utile pour placer le logo CETIM dans une capsule blanche.
    """
    if overlay_rgba is None:
        return background_bgr

    h0, w0 = overlay_rgba.shape[:2]

    max_w = max(1, int(box_w - 2 * margin_x))
    max_h = max(1, int(box_h - 2 * margin_y))

    scale = min(max_w / w0, max_h / h0)

    target_w = int(w0 * scale)
    target_h = int(h0 * scale)

    x = int(box_x + (box_w - target_w) / 2)
    y = int(box_y + (box_h - target_h) / 2)

    return overlay_rgba_image(
        background_bgr,
        overlay_rgba,
        x=x,
        y=y,
        alpha_scale=alpha_scale,
        target_w=target_w,
        target_h=target_h,
    )


# ============================================================
# 4) COMPOSANTS DASHBOARD : PANNEAUX, HEADER, LIGNES
# ============================================================

# ------------------------------------------------------------
# Dessine un panneau type dashboard.
# ------------------------------------------------------------
def draw_panel_box(
    img,
    x,
    y,
    w,
    h,
    title=None,
    panel_color=(10, 35, 65),
    border_color=(50, 100, 150),
    text_color=(235, 240, 245),
    radius=10,
):
    """
    Dessine un panneau dashboard avec fond, bordure et titre optionnel.
    """
    x, y, w, h = int(x), int(y), int(w), int(h)

    draw_rounded_rect(
        img,
        (x, y),
        (x + w, y + h),
        color=panel_color,
        radius=radius,
        thickness=-1,
    )

    draw_rounded_rect(
        img,
        (x, y),
        (x + w, y + h),
        color=border_color,
        radius=radius,
        thickness=1,
    )

    if title is not None:
        draw_text_pil(
            img,
            title.upper(),
            x=x + 14,
            y=y + 10,
            color=text_color,
            size=15,
            bold=True,
            anchor="la",
        )

        cv2.line(
            img,
            (x + 12, y + 29),
            (x + w - 12, y + 29),
            border_color,
            1,
            cv2.LINE_AA,
        )

    return img


# ------------------------------------------------------------
# Dessine la barre haute avec logo et titre.
# ------------------------------------------------------------
def draw_header_bar(
    img,
    title,
    logo_rgba=None,
    header_h=56,
    bg_color=(7, 32, 60),
    text_color=(235, 240, 245),
    accent_color=(115, 210, 255),
):
    """
    Header moderne :
    - fond bleu fonce ;
    - capsule blanche pour logo CETIM ;
    - titre blanc centre verticalement.
    """
    _, w = img.shape[:2]

    cv2.rectangle(
        img,
        (0, 0),
        (w, header_h),
        bg_color,
        -1,
        cv2.LINE_AA,
    )

    cv2.line(
        img,
        (0, header_h - 1),
        (w, header_h - 1),
        accent_color,
        1,
        cv2.LINE_AA,
    )

    # Capsule logo.
    logo_box_x = 16
    logo_box_y = 8
    logo_box_w = 150
    logo_box_h = header_h - 16

    draw_rounded_rect(
        img,
        (logo_box_x, logo_box_y),
        (logo_box_x + logo_box_w, logo_box_y + logo_box_h),
        color=(250, 250, 250),
        radius=8,
        thickness=-1,
    )

    draw_rounded_rect(
        img,
        (logo_box_x, logo_box_y),
        (logo_box_x + logo_box_w, logo_box_y + logo_box_h),
        color=accent_color,
        radius=8,
        thickness=1,
    )

    if logo_rgba is not None:
        overlay_rgba_fit_center(
            img,
            logo_rgba,
            box_x=logo_box_x,
            box_y=logo_box_y,
            box_w=logo_box_w,
            box_h=logo_box_h,
            margin_x=12,
            margin_y=7,
            alpha_scale=1.0,
        )
    else:
        draw_text_pil(
            img,
            "CETIM",
            x=logo_box_x + logo_box_w // 2,
            y=logo_box_y + logo_box_h // 2,
            color=(80, 50, 15),
            size=21,
            bold=True,
            anchor="mm",
        )

    # Titre.
    title_x = logo_box_x + logo_box_w + 34

    draw_text_pil(
        img,
        title,
        x=title_x,
        y=header_h // 2 + 1,
        color=text_color,
        size=23,
        bold=True,
        anchor="lm",
    )

    return img


# ------------------------------------------------------------
# Dessine les lignes cle / valeur du panneau d'informations.
# ------------------------------------------------------------
def draw_key_value_rows(
    img,
    rows,
    x,
    y,
    w,
    row_h=24,
    key_color=(230, 235, 240),
    value_color=(150, 230, 120),
    font_scale=0.43,
):
    """
    Liste cle / valeur rendue avec police moderne.
    font_scale est garde pour compatibilite, mais non utilise directement.

    rows accepte :
        [(cle, valeur), ...]
        ou
        [(cle, valeur, couleur_valeur), ...]
    """
    yy = int(y)

    key_size = 15
    value_size = 15

    for row in rows:
        if len(row) == 2:
            key, value = row
            val_color = value_color
        else:
            key, value, val_color = row

        draw_text_pil(
            img,
            str(key),
            x=int(x),
            y=yy,
            color=key_color,
            size=key_size,
            bold=False,
            anchor="la",
        )

        value = str(value)
        tw, _ = text_size_pil(value, size=value_size, bold=True)

        draw_text_pil(
            img,
            value,
            x=int(x + w - tw),
            y=yy,
            color=val_color,
            size=value_size,
            bold=True,
            anchor="la",
        )

        yy += row_h

    return img


# ------------------------------------------------------------
# Dessine un bouton type pilule ON/OFF.
# ------------------------------------------------------------
def draw_toggle_pill(
    img,
    x,
    y,
    is_on,
    label_on="ACTIF",
    label_off="OFF",
    on_color=(70, 180, 70),
    off_color=(90, 90, 90),
    text_color=(255, 255, 255),
):
    """
    Dessine un petit badge ON/OFF.
    Le texte interne reste en OpenCV car il est court et bien lisible.
    """
    label = label_on if is_on else label_off
    color = on_color if is_on else off_color

    font = cv2.FONT_HERSHEY_SIMPLEX
    fs = 0.42
    th = 1

    (tw, th_text), _ = cv2.getTextSize(label, font, fs, th)

    pad_x = 10
    pad_y = 5
    w = tw + 2 * pad_x
    h = th_text + 2 * pad_y

    draw_rounded_rect(
        img,
        (x, y),
        (x + w, y + h),
        color=color,
        radius=6,
        thickness=-1,
    )

    cv2.putText(
        img,
        label,
        (x + pad_x, y + pad_y + th_text),
        font,
        fs,
        text_color,
        th,
        cv2.LINE_AA,
    )

    return img


# ------------------------------------------------------------
# Dessine une ligne de reglage type slider.
# ------------------------------------------------------------
def draw_slider_like_row(
    img,
    x,
    y,
    w,
    label,
    value_text,
    ratio,
    line_color=(110, 170, 220),
    knob_color=(240, 245, 250),
    text_color=(235, 240, 245),
    value_box_color=(20, 55, 90),
):
    """
    Dessine une ligne type reglage : label + valeur + barre + curseur.
    """
    ratio = float(np.clip(ratio, 0.0, 1.0))

    font = cv2.FONT_HERSHEY_SIMPLEX

    cv2.putText(
        img,
        label,
        (x, y),
        font,
        0.42,
        text_color,
        1,
        cv2.LINE_AA,
    )

    # Valeur a droite.
    box_w = 62
    box_h = 22
    box_x = x + w - box_w
    box_y = y - 16

    draw_rounded_rect(
        img,
        (box_x, box_y),
        (box_x + box_w, box_y + box_h),
        color=value_box_color,
        radius=5,
        thickness=-1,
    )

    cv2.rectangle(
        img,
        (box_x, box_y),
        (box_x + box_w, box_y + box_h),
        (80, 130, 180),
        1,
        cv2.LINE_AA,
    )

    (tw, _), _ = cv2.getTextSize(value_text, font, 0.40, 1)

    cv2.putText(
        img,
        value_text,
        (box_x + box_w - tw - 5, y),
        font,
        0.40,
        text_color,
        1,
        cv2.LINE_AA,
    )

    # Barre.
    bar_x = x
    bar_y = y + 18
    bar_w = w - 8

    cv2.line(
        img,
        (bar_x, bar_y),
        (bar_x + bar_w, bar_y),
        line_color,
        2,
        cv2.LINE_AA,
    )

    kx = int(bar_x + ratio * bar_w)

    cv2.circle(
        img,
        (kx, bar_y),
        5,
        knob_color,
        -1,
        cv2.LINE_AA,
    )

    return img


# ------------------------------------------------------------
# Dessine la barre inferieure : niveau, dynamique, couleur, trigger.
# ------------------------------------------------------------
def draw_bottom_level_bar(
    img,
    x,
    y,
    w,
    h,
    level_db,
    trigger_db,
    bf_active,
    dyn_dB=3.0,
    label="Niveau bande f (dB)",
    colorbar_width_ratio=0.52,
):
    """
    Barre bas :
        Niveau bande f (dB)  11.5 dB    -3 dB [barre couleur] 0 dB    TRIG OFF

    La barre couleur indique la dynamique relative :
        gauche = -dyn_dB
        droite = 0 dB
    """
    x, y, w, h = int(x), int(y), int(w), int(h)

    panel_color = (62, 32, 8)       # BGR = bleu fonce coherent avec le dashboard.
    border_color = (200, 150, 80)
    text_color = (235, 240, 245)
    yellow = (0, 255, 255)

    draw_panel_box(
        img,
        x,
        y,
        w,
        h,
        title=None,
        panel_color=panel_color,
        border_color=border_color,
        text_color=text_color,
        radius=8,
    )

    # Axe vertical commun : tous les textes et la barre sont centres dessus.
    mid_y = y + h // 2

    # Texte "Niveau bande" et valeur jaune.
    label_x = x + 20

    draw_text_pil(
        img,
        label,
        x=label_x,
        y=mid_y,
        color=text_color,
        size=15,
        bold=False,
        anchor="lm",
    )

    label_w, _ = text_size_pil(label, size=15, bold=False)

    level_txt = f"{level_db:.1f} dB"
    level_x = label_x + label_w + 24

    draw_text_pil(
        img,
        level_txt,
        x=level_x,
        y=mid_y,
        color=yellow,
        size=17,
        bold=False,
        anchor="lm",
    )

    # Libelles de dynamique relative.
    dyn_left_txt = f"-{float(dyn_dB):.1f} dB"

    if abs(float(dyn_dB) - round(float(dyn_dB))) < 1e-6:
        dyn_left_txt = f"-{int(round(float(dyn_dB)))} dB"

    dyn_right_txt = "0 dB"

    # Zone trigger decalee a droite.
    trig_x = x + w - 185
    max_bar_right = trig_x - 40

    # Zone barre couleur.
    colorbar_area_x = level_x + 145

    left_w, _ = text_size_pil(dyn_left_txt, size=14, bold=False)
    right_w, _ = text_size_pil(dyn_right_txt, size=14, bold=False)

    left_txt_x = colorbar_area_x

    bar_h = 18
    bar_y = mid_y - bar_h // 2

    bar_x = left_txt_x + left_w + 12

    available_bar_w = max_bar_right - bar_x - right_w - 14
    bar_w = int(max(150, available_bar_w * colorbar_width_ratio))
    bar_w = min(bar_w, max(120, available_bar_w))

    right_txt_x = bar_x + bar_w + 12

    # Texte gauche de dynamique : -dyn dB.
    draw_text_pil(
        img,
        dyn_left_txt,
        x=left_txt_x,
        y=mid_y,
        color=text_color,
        size=14,
        bold=False,
        anchor="lm",
    )

    # Barre couleur relative.
    grad = np.linspace(0, 255, bar_w, dtype=np.uint8).reshape(1, -1)
    grad = np.repeat(grad, bar_h, axis=0)
    colorbar = cv2.applyColorMap(grad, cv2.COLORMAP_JET)

    img[bar_y:bar_y + bar_h, bar_x:bar_x + bar_w] = colorbar

    cv2.rectangle(
        img,
        (bar_x, bar_y),
        (bar_x + bar_w, bar_y + bar_h),
        (95, 155, 205),
        1,
        cv2.LINE_AA,
    )

    # Texte droite de dynamique : 0 dB.
    draw_text_pil(
        img,
        dyn_right_txt,
        x=right_txt_x,
        y=mid_y,
        color=text_color,
        size=14,
        bold=False,
        anchor="lm",
    )

    # Trigger : texte + bouton decales ensemble a droite.
    draw_text_pil(
        img,
        "TRIG",
        x=trig_x,
        y=mid_y,
        color=text_color,
        size=15,
        bold=False,
        anchor="lm",
    )

    draw_toggle_pill(
        img,
        trig_x + 60,
        mid_y - 11,
        is_on=bf_active,
        label_on="ACTIF",
        label_off="OFF",
    )

    return img


# ============================================================
# 5) HUD CAMERA / RACCOURCIS / ELEMENTS LEGACY
# ============================================================

# ------------------------------------------------------------
# Ancien panneau HUD compact semi-transparent.
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Ancien footer d'aide clavier.
# ------------------------------------------------------------
def draw_footer(img, text, show=True):
    """
    Affiche une ligne d'aide discrete en bas.
    """
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


# ------------------------------------------------------------
# Ancien badge de statut haut droit.
# ------------------------------------------------------------
def draw_status_badge(img, text, color, x=None, y=10):
    """
    Affiche un petit badge en haut a droite.
    """
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


# ------------------------------------------------------------
# Convertit un booleen en ON/OFF.
# ------------------------------------------------------------
def format_on_off(value):
    """
    Retourne ON/OFF pour affichage.
    """
    return "ON" if value else "OFF"


# ------------------------------------------------------------
# Dessine le HUD transparent de raccourcis.
# ------------------------------------------------------------
def draw_shortcuts_box(
    img,
    x,
    y,
    shortcuts,
    title="Raccourcis",
    panel_color=(0, 0, 0),
    text_color=(235, 240, 245),
    accent_color=(115, 210, 255),
    alpha=0.45,
):
    """
    Dessine un petit HUD transparent de raccourcis.

    shortcuts = [
        ("q", "quitter"),
        ("a", "algo"),
        ...
    ]
    """
    line_h = 20
    pad = 10
    w = 205
    h = pad * 2 + 22 + line_h * len(shortcuts)

    # Fond transparent.
    overlay = img.copy()
    draw_rounded_rect(
        overlay,
        (x, y),
        (x + w, y + h),
        color=panel_color,
        radius=8,
        thickness=-1,
    )

    img[:] = cv2.addWeighted(
        overlay,
        alpha,
        img,
        1.0 - alpha,
        0,
    )

    cv2.putText(
        img,
        title.upper(),
        (x + pad, y + 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        accent_color,
        1,
        cv2.LINE_AA,
    )

    yy = y + 42

    for key, desc in shortcuts:
        cv2.putText(
            img,
            str(key),
            (x + pad, yy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            accent_color,
            1,
            cv2.LINE_AA,
        )

        cv2.putText(
            img,
            str(desc),
            (x + pad + 45, yy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            text_color,
            1,
            cv2.LINE_AA,
        )

        yy += line_h

    return img


# ============================================================
# 6) GESTION CLAVIER
# ============================================================

# ------------------------------------------------------------
# Gestion centralisee des touches clavier live.
# ------------------------------------------------------------
# ============================================================
# GESTION CLAVIER : TOUCHES DU LIVE
# ============================================================

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

    Raccourcis principaux :
        q       : quitter
        p       : afficher / masquer HUD
        m       : miroir image
        t / y   : seuil trigger - / +
        , / ;   : frequence - / +
        x / w   : dynamique - / +
        - / +   : transparence - / +
        g / G   : gamma transparence - / +
        j       : colormap
        d       : afficher max
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

    # ------------------------------------------------------------
    # Trigger : t / y
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # Dynamique couleur : x / w
    # x = dynamique plus faible
    # w = dynamique plus grande
    # ------------------------------------------------------------
    elif key == ord("x"):
        dyn_dB = max(1.0, dyn_dB - 1.0)
        print(f"[INFO] Dynamique={dyn_dB:.1f} dB")

    elif key == ord("w"):
        dyn_dB = min(60.0, dyn_dB + 1.0)
        print(f"[INFO] Dynamique={dyn_dB:.1f} dB")

    # ------------------------------------------------------------
    # Transparence overlay : - / +
    # - = moins visible
    # + = plus visible
    # ------------------------------------------------------------
    elif key == ord("-"):
        alpha_scale = max(0.0, alpha_scale - 0.05)
        print(f"[INFO] Transparence alpha={alpha_scale:.2f}")

    elif key == ord("+") or key == ord("="):
        alpha_scale = min(1.0, alpha_scale + 0.05)
        print(f"[INFO] Transparence alpha={alpha_scale:.2f}")

    # ------------------------------------------------------------
    # Gamma transparence : g / G
    # ------------------------------------------------------------
    elif key == ord("g"):
        alpha_gamma = max(0.2, alpha_gamma - 0.05)
        print(f"[INFO] Gamma alpha={alpha_gamma:.2f}")

    elif key == ord("G"):
        alpha_gamma = min(3.0, alpha_gamma + 0.05)
        print(f"[INFO] Gamma alpha={alpha_gamma:.2f}")

    # ------------------------------------------------------------
    # Colormap / max
    # ------------------------------------------------------------
    elif key == ord("j"):
        use_turbo = not use_turbo
        print(f"[INFO] use_turbo={use_turbo}")

    elif key == ord("d"):
        show_max = not show_max
        print(f"[INFO] show_max={show_max}")

    # ------------------------------------------------------------
    # Frequence : , / ;
    # , = frequence precedente
    # ; = frequence suivante
    # ------------------------------------------------------------
    elif key == ord(","):
        f_center = max(config.f_min, f_center - config.f_step)
        print(f"[INFO] Frequence={f_center:.0f} Hz")

    elif key == ord(";"):
        f_center = min(config.f_max, f_center + config.f_step)
        print(f"[INFO] Frequence={f_center:.0f} Hz")

    return (
        dyn_dB,
        alpha_scale,
        alpha_gamma,
        use_turbo,
        show_max,
        f_center,
        quit_requested,
    )

# ============================================================
# INDICATEUR ENREGISTREMENT
# ============================================================

def draw_recording_indicator(
    img,
    is_recording,
    x=None,
    y=12,
    text_color=(255, 255, 255),
):
    """
    Affiche un indicateur d'enregistrement.

    Si is_recording :
        cercle rouge + texte REC + carre stop
    Sinon :
        carre gris + texte STOP
    """
    h_img, w_img = img.shape[:2]

    if x is None:
        x = w_img - 118

    box_w = 104
    box_h = 30

    bg_color = (30, 30, 30)
    border_color = (120, 120, 120)

    draw_rounded_rect(
        img,
        (x, y),
        (x + box_w, y + box_h),
        color=bg_color,
        radius=7,
        thickness=-1,
    )

    draw_rounded_rect(
        img,
        (x, y),
        (x + box_w, y + box_h),
        color=border_color,
        radius=7,
        thickness=1,
    )

    cy = y + box_h // 2

    if is_recording:
        # cercle rouge REC
        cv2.circle(
            img,
            (x + 17, cy),
            6,
            (0, 0, 255),
            -1,
            cv2.LINE_AA,
        )

        draw_text_pil(
            img,
            "REC",
            x=x + 31,
            y=cy,
            color=text_color,
            size=14,
            bold=True,
            anchor="lm",
        )

        # carre stop rouge
        cv2.rectangle(
            img,
            (x + 76, cy - 6),
            (x + 88, cy + 6),
            (0, 0, 255),
            -1,
            cv2.LINE_AA,
        )

    else:
        # carre gris stop
        cv2.rectangle(
            img,
            (x + 13, cy - 6),
            (x + 25, cy + 6),
            (120, 120, 120),
            -1,
            cv2.LINE_AA,
        )

        draw_text_pil(
            img,
            "STOP",
            x=x + 36,
            y=cy,
            color=(210, 210, 210),
            size=14,
            bold=True,
            anchor="lm",
        )

    return img