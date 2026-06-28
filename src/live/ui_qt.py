# -*- coding: utf-8 -*-
"""
ui_qt.py — "display" PySide6 du live (equivalent Qt de display.py/ui.py).

Regroupe toute l'interface graphique PySide6 :
- helpers (couleurs QSS, Title Case, conversion image -> QPixmap) ;
- AcousticCameraWindow : la fenetre complete (bandeau, image+overlay+HUD,
  panneau de reglages, barre de niveau).

L'affichage est pilote par un QTimer mono-thread ; le calcul est delegue a
LiveEngine (aucun algorithme ici).
"""

import os

# ------------------------------------------------------------------
# matplotlib : forcer le backend non-interactif AVANT d'importer le moteur.
# Des modules (signal_process, visu) appellent matplotlib.use('Qt5Agg') a
# l'import ; comme on n'affiche aucune figure matplotlib, on neutralise ces
# bascules pour eviter de charger un second binding Qt a cote de PySide6.
# (Doit s'executer avant l'import de live_engine, qui tire la chaine moteur.)
# ------------------------------------------------------------------
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
matplotlib.use = lambda *a, **k: None  # noqa: E731 (neutralisation volontaire)

import time

import numpy as np
import cv2

from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QFrame,
    QSlider,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSizePolicy,
)

from src.live.live_engine import LiveEngine
from src.live.display import process_keyboard_from_key, SHORTCUTS


# ==================================================================
# Helpers UI
# ==================================================================
def rgb_css(color, default=(8, 42, 78)):
    """[R,G,B] (YAML) -> 'rgb(r,g,b)' pour QSS."""
    try:
        r, g, b = color
    except Exception:
        r, g, b = default
    return f"rgb({int(r)},{int(g)},{int(b)})"


def title_case(text):
    """Majuscule a chaque mot (separateurs espace et /)."""
    out = []
    for word in str(text).split(" "):
        out.append("/".join(p[:1].upper() + p[1:] if p else p
                            for p in word.split("/")))
    return " ".join(out)


def bgr_to_pixmap(frame_bgr):
    """ndarray BGR contigu -> QPixmap (via QImage Format_BGR888)."""
    frame_bgr = np.ascontiguousarray(frame_bgr)
    h, w = frame_bgr.shape[:2]
    qimg = QImage(frame_bgr.data, w, h, 3 * w, QImage.Format_BGR888).copy()
    return QPixmap.fromImage(qimg)


# ==================================================================
# Fenetre principale
# ==================================================================
class AcousticCameraWindow(QMainWindow):

    HEADER_SIDE_W = 200   # zones gauche/droite egales -> titre centre fenetre
    COLORBAR_W = 260      # largeur FIXE de la colorbar
    COLORBAR_H = 18

    # Nb de frames BF mesurees avant de juger la faisabilite des modes.
    PROC_WARMUP = 15
    # Marge : le calcul par frame doit tenir dans ce ratio de Th pour etre tenable.
    PROC_MARGIN = 0.85

    # Modes d'acquisition par defaut (si absents du YAML) : couples (Tw, Th).
    DEFAULT_MODES = [
        {"label": "Lent", "Tw": 0.5, "Th": 0.1, "delta_f": 20.0},
        {"label": "Normal", "Tw": 0.2, "Th": 0.05, "delta_f": 25.0},
        {"label": "Rapide", "Tw": 0.1, "Th": 0.02, "delta_f": 40.0},
    ]

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.engine = LiveEngine(config)
        self.state = self.engine.state

        self._last_blended = None
        self._cur_pixmap = None
        self._syncing = False
        self._cmap_turbo_cache = None
        self._camera_only_cache = None
        self._proc_ms = 0.0           # temps de calcul estime par frame (EMA)
        self._proc_n = 0              # nb de frames BF mesurees
        self._modes_evaluated = False  # faisabilite des modes deja jugee ?
        # decomposition du temps par etape (EMA, ms) pour le profilage
        self._stage_ms = {"cam": 0.0, "csm": 0.0, "bf": 0.0, "ov": 0.0, "ui": 0.0}

        # Bornes de frequence COMMUNES au clavier et au slider :
        #   - basse : f_min_live (repli f_min)
        #   - haute : f_max (= f_max_factor * Fe, cf config), plafonnee a Nyquist.
        # Le PAS differe : clavier = config.f_step (100 Hz, via handle_key),
        # slider = config.f_slider_step (defaut = moitie de f_step, ~50 Hz).
        self.f_lo = float(getattr(config, "f_min_live", config.f_min))
        self.f_hi = min(float(config.f_max), float(config.Fe) / 2.0)
        self.f_slider_step = float(
            getattr(config, "f_slider_step", float(config.f_step) / 2.0))
        if self.f_hi <= self.f_lo:
            self.f_hi = self.f_lo + self.f_slider_step
        self.n_freq_steps = max(
            1, int(round((self.f_hi - self.f_lo) / self.f_slider_step)))

        # Modes d'acquisition (couples Tw/Th) selectionnables dans Informations.
        self.modes = self._load_modes(config)
        self._mode_index = self._match_mode_index(config)

        self.setWindowTitle("Camera acoustique live — PySide6")
        self._build_ui()
        self._sync_from_state()

        # QTimer : pilote la boucle live, mono-thread.
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(self._timer_interval_ms())

        # Les raccourcis clavier doivent fonctionner meme si un slider ou un
        # combo a le focus -> filtre d'evenements au niveau de l'application.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    # --------------------------------------------------------------
    # Construction de l'interface
    # --------------------------------------------------------------
    def _build_ui(self):
        c = self.config
        bg = rgb_css(getattr(c, "ui_bg_color", [5, 28, 55]), (5, 28, 55))
        panel = rgb_css(getattr(c, "ui_panel_color", [8, 42, 78]), (8, 42, 78))
        header = rgb_css(getattr(c, "ui_header_color", [0, 48, 85]), (0, 48, 85))
        border = rgb_css(getattr(c, "ui_panel_border_color", [80, 150, 200]),
                         (80, 150, 200))
        text = rgb_css(getattr(c, "ui_text_color", [235, 240, 245]),
                       (235, 240, 245))

        # IMPORTANT : pas de background-color sur QWidget global (boites opaques).
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {bg}; }}
            QFrame#Header, QFrame#RightPanel, QFrame#BottomBar {{
                background-color: {panel};
                border: 1px solid {border};
            }}
            QFrame#Header {{ background-color: {header}; border: none;
                             border-bottom: 1px solid {border}; }}
            QGroupBox {{
                background-color: {panel};
                border: 1px solid {border};
                border-radius: 8px;
                margin-top: 16px;
                color: {text};
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin; left: 12px; padding: 0 4px;
            }}
            QLabel, QCheckBox {{ background: transparent; color: {text}; }}
            QComboBox {{ color: {text}; background-color: {bg};
                         border: 1px solid {border}; border-radius: 4px;
                         padding: 2px 6px; }}
            QComboBox QAbstractItemView {{ background-color: {bg};
                         color: {text}; selection-background-color: {border}; }}
            QComboBox:disabled {{ color: rgb(110,120,135);
                         background-color: rgb(18,32,52);
                         border-color: rgb(45,65,90); }}
            QSlider::groove:horizontal {{ height: 5px; background: rgb(35,60,90);
                         border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: rgb(80,150,210);
                         border-radius: 2px; }}
            QSlider::add-page:horizontal {{ background: rgb(35,60,90);
                         border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: rgb(120,185,235);
                         border: 1px solid rgb(170,210,240); width: 12px;
                         margin: -5px 0; border-radius: 6px; }}
            QSlider::handle:horizontal:hover {{ background: rgb(150,205,245); }}
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header_frame = self._build_header()
        root.addWidget(self.header_frame)

        middle = QHBoxLayout()
        middle.setContentsMargins(8, 8, 8, 8)
        middle.setSpacing(8)
        middle.addWidget(self._build_image_area(), stretch=1)
        self.right_panel = self._build_right_panel()
        middle.addWidget(self.right_panel, stretch=0)
        root.addLayout(middle, stretch=1)

        self.bottom_bar = self._build_bottom_bar()
        root.addWidget(self.bottom_bar)

        self.resize(1040, 660)

    def _build_header(self):
        frame = QFrame()
        frame.setObjectName("Header")
        frame.setFixedHeight(int(getattr(self.config, "ui_header_h", 56)) + 8)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 6, 12, 6)

        # Zone gauche : capsule logo (largeur fixe).
        left = QWidget()
        left.setFixedWidth(self.HEADER_SIDE_W)
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.addWidget(self._build_logo_capsule(), alignment=Qt.AlignLeft)
        left_lay.addStretch(1)
        lay.addWidget(left)

        # Titre centre.
        title = QLabel("CAMERA ACOUSTIQUE LIVE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; "
                            "letter-spacing: 1px; background: transparent;")
        lay.addWidget(title, stretch=1)

        # Zone droite : indicateur REC (meme largeur que gauche -> titre centre).
        right = QWidget()
        right.setFixedWidth(self.HEADER_SIDE_W)
        right_lay = QHBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.addStretch(1)
        self.rec_label = QLabel()
        self.rec_label.setFixedSize(104, 30)
        self.rec_label.setAlignment(Qt.AlignCenter)
        right_lay.addWidget(self.rec_label, alignment=Qt.AlignRight)
        lay.addWidget(right)

        self._update_rec_indicator(False)
        return frame

    def _build_logo_capsule(self):
        cap_h = int(getattr(self.config, "ui_header_h", 56)) - 8
        cap_w = self.HEADER_SIDE_W - 16

        cap = QFrame()
        cap.setObjectName("LogoCapsule")
        cap.setFixedSize(cap_w, cap_h)
        # Le logo CETIM est bleu marine fonce : invisible sur le bandeau sombre.
        # On lui met une capsule claire pour qu'il ressorte.
        cap.setStyleSheet("QFrame#LogoCapsule { background-color: rgb(245,247,250);"
                          " border-radius: 8px; }")
        cl = QHBoxLayout(cap)
        cl.setContentsMargins(10, 5, 10, 5)

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet("background: transparent;")
        pix = None
        logo_path = getattr(self.config, "cetim_logo_path", None)
        if logo_path is not None and os.path.exists(str(logo_path)):
            p = QPixmap(str(logo_path))
            if not p.isNull():
                # Logo tres large (~7.9:1) : KeepAspectRatio pour le faire tenir
                # ENTIEREMENT dans la capsule (largeur ET hauteur), sans le couper.
                pix = p.scaled(cap_w - 18, cap_h - 12,
                               Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if pix is not None:
            logo.setPixmap(pix)
        else:
            logo.setText("CETIM")
            logo.setStyleSheet("background: transparent; color: rgb(15,50,80);"
                              " font-size: 18px; font-weight: bold;")
        cl.addWidget(logo)
        return cap

    def _build_image_area(self):
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(480, 360)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setStyleSheet("background-color: rgb(0,0,0);")
        lay.addWidget(self.image_label)

        # HUD raccourcis (overlay vectoriel, enfant du label image).
        self.hud = QFrame(self.image_label)
        self.hud.setObjectName("Hud")
        self.hud.setStyleSheet(
            "QFrame#Hud { background-color: rgba(0,0,0,120); border-radius: 8px; }"
            " QLabel { background: transparent; }")
        hud_lay = QGridLayout(self.hud)
        hud_lay.setContentsMargins(10, 8, 12, 8)
        hud_lay.setHorizontalSpacing(10)
        hud_lay.setVerticalSpacing(3)

        title = QLabel("RACCOURCIS")
        title.setStyleSheet("color: rgb(0,220,255); font-weight: bold;"
                            " background: transparent;")
        hud_lay.addWidget(title, 0, 0, 1, 2)

        for i, (key, desc) in enumerate(SHORTCUTS, start=1):
            k = QLabel(str(key))
            k.setStyleSheet("color: rgb(0,220,255); background: transparent;")
            d = QLabel(title_case(desc))
            d.setStyleSheet("color: rgb(240,240,245); background: transparent;")
            hud_lay.addWidget(k, i, 0)
            hud_lay.addWidget(d, i, 1)

        self.hud.adjustSize()
        self.hud.move(12, 12)
        return container

    def _build_right_panel(self):
        frame = QFrame()
        frame.setObjectName("RightPanel")
        frame.setFixedWidth(int(getattr(self.config, "ui_right_panel_w", 250)) + 40)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)

        lay.addWidget(self._build_info_group())
        lay.addWidget(self._build_controls_group())
        lay.addStretch(1)
        return frame

    def _load_modes(self, config):
        """Charge les modes (Tw/Th) du YAML, repli sur DEFAULT_MODES."""
        raw = getattr(config, "modes", None) or self.DEFAULT_MODES
        modes = []
        for m in raw:
            try:
                modes.append({"label": str(m["label"]),
                              "Tw": float(m["Tw"]), "Th": float(m["Th"]),
                              "delta_f": float(m.get("delta_f", config.delta_f))})
            except (TypeError, KeyError, ValueError):
                continue
        return modes or [dict(d) for d in self.DEFAULT_MODES]

    def _match_mode_index(self, config):
        """Indice du mode correspondant aux Tw/Th courants (0 si aucun)."""
        for i, m in enumerate(self.modes):
            if (abs(m["Tw"] - float(config.Tw)) < 1e-9
                    and abs(m["Th"] - float(config.Th)) < 1e-9):
                return i
        return 0

    def _build_info_group(self):
        box = QGroupBox("Informations")
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 8, 12, 10)
        grid.setVerticalSpacing(4)

        self.info_labels = {}
        rows = ["Frequence", "Niveau", "Max BF", "FPS", "Tw", "Th", "Resolution"]
        # Frequence en bleu ; Niveau/Max BF/FPS en blanc gras ; Tw/Th/Resolution
        # (parametres de fenetre, lies au mode) en gris leger.
        val_styles = {
            "Frequence": "color: rgb(70,190,230); font-weight: bold;",
            "Niveau": "color: rgb(235,240,245); font-weight: bold;",
            "Max BF": "color: rgb(235,240,245); font-weight: bold;",
            "FPS": "color: rgb(235,240,245); font-weight: bold;",
            "Tw": "color: rgb(150,165,185); font-weight: normal;",
            "Th": "color: rgb(150,165,185); font-weight: normal;",
            "Resolution": "color: rgb(150,165,185); font-weight: normal;",
        }
        for i, name in enumerate(rows):
            key = QLabel(name)
            if name in ("Tw", "Th", "Resolution"):
                key.setStyleSheet("background: transparent;"
                                  " color: rgb(150,165,185); font-weight: normal;")
            val = QLabel("-")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet("background: transparent; " + val_styles[name])
            grid.addWidget(key, i, 0)
            grid.addWidget(val, i, 1)
            self.info_labels[name] = val
        return box

    def _build_controls_group(self):
        box = QGroupBox("Reglages")
        grid = QGridLayout(box)
        grid.setContentsMargins(12, 8, 12, 10)
        grid.setVerticalSpacing(6)
        row = 0

        # --- sliders ---
        self.freq_slider, self.freq_val = self._add_slider(
            grid, row, "Frequence", 0, self.n_freq_steps, self._on_freq)
        row += 1
        self.dyn_slider, self.dyn_val = self._add_slider(
            grid, row, "Dynamique", 1, 60, self._on_dyn)
        row += 1
        self.alpha_slider, self.alpha_val = self._add_slider(
            grid, row, "Transparence", 0, 100, self._on_alpha)
        row += 1
        trig_max = int(round(float(getattr(self.config, "trig_max_dB", 120.0))))
        self.trig_slider, self.trig_val = self._add_slider(
            grid, row, "Declenchement", 0, trig_max, self._on_trig)
        row += 1

        # --- Mode d'acquisition (Lent/Normal/Rapide), juste sous Declenchement ---
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([m["label"] for m in self.modes])
        self.mode_combo.setCurrentIndex(self._mode_index)  # avant connect : pas de signal
        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        grid.addWidget(QLabel("Mode"), row, 0)
        grid.addWidget(self.mode_combo, row, 1, 1, 2)
        row += 1

        # --- menus deroulants ---
        self.algo_combo = QComboBox()
        self.algo_combo.addItems(["Bartlett", "OBF"])
        self.algo_combo.currentIndexChanged.connect(self._on_algo)
        grid.addWidget(QLabel("Algorithme"), row, 0)
        grid.addWidget(self.algo_combo, row, 1, 1, 2)
        row += 1

        self.source_combo = QComboBox()
        self.source_combo.addItems(
            [f"Source {i + 1}" for i in range(int(self.state.obf_n_modes))])
        self.source_combo.currentIndexChanged.connect(self._on_source)
        grid.addWidget(QLabel("Source OBF"), row, 0)
        grid.addWidget(self.source_combo, row, 1, 1, 2)
        row += 1

        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(["TURBO", "JET"])
        self.cmap_combo.currentIndexChanged.connect(self._on_cmap)
        grid.addWidget(QLabel("Colormap"), row, 0)
        grid.addWidget(self.cmap_combo, row, 1, 1, 2)
        row += 1

        # --- cases a cocher ---
        self.mirror_check = QCheckBox("Miroir")
        self.mirror_check.toggled.connect(self._on_mirror)
        grid.addWidget(self.mirror_check, row, 0, 1, 3)
        row += 1

        self.cross_check = QCheckBox("Croix du max")
        self.cross_check.toggled.connect(self._on_cross)
        grid.addWidget(self.cross_check, row, 0, 1, 3)
        row += 1

        # La colonne du slider (1) s'etire ; les valeurs (col 2) restent fixes.
        grid.setColumnStretch(1, 1)

        self._controls = [
            self.freq_slider, self.dyn_slider, self.alpha_slider,
            self.trig_slider, self.algo_combo, self.source_combo,
            self.cmap_combo, self.mirror_check, self.cross_check,
        ]
        return box

    def _add_slider(self, grid, row, label, lo, hi, slot):
        grid.addWidget(QLabel(label), row, 0)

        sld = QSlider(Qt.Horizontal)
        sld.setMinimum(lo)
        sld.setMaximum(hi)
        sld.valueChanged.connect(slot)
        grid.addWidget(sld, row, 1)

        # Valeur a DROITE du slider, largeur FIXE : la barre ne se redimensionne
        # pas quand la longueur du texte change (ex: 500 Hz -> 4500 Hz).
        val = QLabel("-")
        val.setFixedWidth(72)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val.setStyleSheet("background: transparent; color: rgb(235,240,245);"
                          " font-weight: bold;")
        grid.addWidget(val, row, 2)
        return sld, val

    def _build_bottom_bar(self):
        frame = QFrame()
        frame.setObjectName("BottomBar")
        frame.setFixedHeight(int(getattr(self.config, "ui_bottom_bar_h", 54)) + 6)
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(16, 6, 16, 6)
        lay.setSpacing(10)

        yc = Qt.AlignVCenter

        # --- Niveau bande f (dB) (a gauche), comme le dashboard OpenCV ---
        lbl = QLabel("Niveau bande f (dB)")
        lbl.setStyleSheet("background: transparent;")
        lay.addWidget(lbl, 0, yc)
        self.level_value = QLabel("-- dB")
        self.level_value.setFixedWidth(78)   # largeur fixe -> colorbar stable
        self.level_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.level_value.setStyleSheet(
            "background: transparent; color: rgb(255,235,90); font-weight: bold;")
        lay.addWidget(self.level_value, 0, yc)

        lay.addStretch(1)

        # --- Colorbar CENTREE, bornes -dyn dB / 0 dB, LARGEUR FIXE ---
        self.dyn_left_label = QLabel("-3 dB")
        self.dyn_left_label.setFixedWidth(52)
        self.dyn_left_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.dyn_left_label.setStyleSheet("background: transparent;")
        lay.addWidget(self.dyn_left_label, 0, yc)

        self.colorbar_label = QLabel()
        self.colorbar_label.setFixedSize(self.COLORBAR_W, self.COLORBAR_H)
        self.colorbar_label.setStyleSheet("background: transparent;")
        lay.addWidget(self.colorbar_label, 0, yc)

        self.dyn_right_label = QLabel("0 dB")
        self.dyn_right_label.setFixedWidth(44)
        self.dyn_right_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.dyn_right_label.setStyleSheet("background: transparent;")
        lay.addWidget(self.dyn_right_label, 0, yc)

        lay.addStretch(1)

        # --- Max BF ---
        mbl = QLabel("Max BF")
        mbl.setStyleSheet("background: transparent;")
        lay.addWidget(mbl, 0, yc)
        self.maxbf_value = QLabel("-- dB")
        self.maxbf_value.setFixedWidth(78)   # largeur fixe -> colorbar stable
        self.maxbf_value.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.maxbf_value.setStyleSheet(
            "background: transparent; color: rgb(255,235,90); font-weight: bold;")
        lay.addWidget(self.maxbf_value, 0, yc)

        # --- TRIG + pilule ACTIF/OFF ---
        lay.addSpacing(18)
        trig_lbl = QLabel("TRIG")
        trig_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(trig_lbl, 0, yc)
        self.trig_pill = QLabel("OFF")
        self.trig_pill.setAlignment(Qt.AlignCenter)
        self.trig_pill.setFixedSize(64, 26)
        lay.addWidget(self.trig_pill, 0, yc)

        self._set_colorbar(self.state.use_turbo)
        self._update_trig_pill(False)
        return frame

    # --------------------------------------------------------------
    # Colorbar / indicateurs
    # --------------------------------------------------------------
    def _set_colorbar(self, use_turbo):
        ramp = np.linspace(0, 255, self.COLORBAR_W, dtype=np.uint8).reshape(1, -1)
        ramp = np.repeat(ramp, self.COLORBAR_H, axis=0)
        cmap = cv2.COLORMAP_TURBO if use_turbo else cv2.COLORMAP_JET
        bar = np.ascontiguousarray(cv2.applyColorMap(ramp, cmap))
        self.colorbar_label.setPixmap(bgr_to_pixmap(bar))
        self._cmap_turbo_cache = bool(use_turbo)

    def _update_rec_indicator(self, is_recording):
        if is_recording:
            self.rec_label.setText("● REC")
            self.rec_label.setStyleSheet(
                "background-color: rgb(40,40,40); color: rgb(255,80,80);"
                " border: 1px solid rgb(255,80,80); border-radius: 7px;"
                " font-weight: bold;")
        else:
            self.rec_label.setText("■ STOP")
            self.rec_label.setStyleSheet(
                "background-color: rgb(40,40,40); color: rgb(210,210,210);"
                " border: 1px solid rgb(120,120,120); border-radius: 7px;")

    def _update_trig_pill(self, active):
        if active:
            self.trig_pill.setText("ACTIF")
            self.trig_pill.setStyleSheet(
                "background-color: rgb(70,180,70); color: white;"
                " border-radius: 7px; font-weight: bold;")
        else:
            self.trig_pill.setText("OFF")
            self.trig_pill.setStyleSheet(
                "background-color: rgb(90,90,90); color: white;"
                " border-radius: 7px;")

    def _apply_camera_only(self, on):
        """
        Mode 'camera seule' (touche c) : masque bandeau / panneau / barre du bas
        et passe la fenetre en plein ecran sur l'image. Echap ou c pour sortir.
        """
        self.header_frame.setVisible(not on)
        self.right_panel.setVisible(not on)
        self.bottom_bar.setVisible(not on)
        if on:
            self.showFullScreen()
        else:
            self.showNormal()

    def _grab_dashboard_bgr(self):
        """Capture le widget central (dashboard complet affiche) en ndarray BGR."""
        qimg = self.centralWidget().grab().toImage().convertToFormat(
            QImage.Format_RGB888)
        w, h = qimg.width(), qimg.height()
        bpl = qimg.bytesPerLine()
        buf = np.frombuffer(qimg.constBits(), dtype=np.uint8, count=bpl * h)
        rgb = buf.reshape(h, bpl)[:, : w * 3].reshape(h, w, 3)
        return np.ascontiguousarray(rgb[:, :, ::-1])  # RGB -> BGR

    # --------------------------------------------------------------
    # Boucle live (QTimer)
    # --------------------------------------------------------------
    def _timer_interval_ms(self):
        """Cadence d'affichage = pas de mise a jour Th, borne a [15, 100] ms."""
        return int(min(100, max(15, float(self.config.Th) * 1000.0)))

    def update_frame(self):
        blended, info = self.engine.step()
        self._last_blended = blended

        t_ui0 = time.perf_counter()
        self._cur_pixmap = bgr_to_pixmap(blended)
        self._refresh_image()
        self._sync_from_state(info)

        # Enregistre le DASHBOARD complet affiche (pas juste l'image centrale),
        # une fois l'UI a jour. Capture seulement si l'enregistrement est actif.
        if self.state.recorder.is_recording:
            self.state.recorder.write(self._grab_dashboard_bgr())
        ui_ms = (time.perf_counter() - t_ui0) * 1000.0

        # Estimation du temps de calcul par frame (hors attente audio) sur les
        # frames ou le beamforming tourne (cas le plus lourd). Apres un warmup,
        # on desactive les modes que la machine ne peut pas tenir (busy > Th).
        if info.get("bf_active"):
            proc = float(info.get("busy_ms", 0.0)) + ui_ms
            first = self._proc_n == 0
            self._proc_ms = proc if first else 0.8 * self._proc_ms + 0.2 * proc

            # decomposition par etape (camera / CSM / beamforming / overlay / UI)
            samples = (("cam", info.get("cam_ms", 0.0)),
                       ("csm", info.get("csm_ms", 0.0)),
                       ("bf", info.get("bf_ms", 0.0)),
                       ("ov", info.get("ov_ms", 0.0)),
                       ("ui", ui_ms))
            for k, v in samples:
                v = float(v)
                self._stage_ms[k] = v if first else 0.8 * self._stage_ms[k] + 0.2 * v

            self._proc_n += 1
            if not self._modes_evaluated and self._proc_n >= self.PROC_WARMUP:
                s = self._stage_ms
                print(f"[INFO] Temps/frame ~{self._proc_ms:.0f} ms : "
                      f"camera {s['cam']:.0f} | CSM {s['csm']:.0f} | "
                      f"beamforming {s['bf']:.0f} | overlay {s['ov']:.0f} | "
                      f"UI/Qt {s['ui']:.0f} ms")
                self._evaluate_modes()
                self._modes_evaluated = True

    def _refresh_image(self):
        if self._cur_pixmap is None:
            return
        self.image_label.setPixmap(self._cur_pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        ))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_image()

    # --------------------------------------------------------------
    # Synchro etat -> controles (signaux bloques)
    # --------------------------------------------------------------
    def _sync_from_state(self, info=None):
        self._syncing = True
        for w in getattr(self, "_controls", []):
            w.blockSignals(True)

        st = self.state
        cfg = self.config

        fi = int(round((st.f_center - self.f_lo) / self.f_slider_step))
        self.freq_slider.setValue(int(np.clip(fi, 0, self.n_freq_steps)))
        self.freq_val.setText(f"{st.f_center:.0f} Hz")

        self.dyn_slider.setValue(int(round(st.dyn_dB)))
        self.dyn_val.setText(f"{st.dyn_dB:.0f} dB")

        self.alpha_slider.setValue(int(round(st.alpha_scale * 100)))
        self.alpha_val.setText(f"{int(round(st.alpha_scale * 100))} %")

        self.trig_slider.setValue(int(round(cfg.level_threshold_dB)))
        self.trig_val.setText(f"{cfg.level_threshold_dB:.0f} dB")

        self.algo_combo.setCurrentIndex(int(st.algorithm_index))
        is_obf = (st.algorithm == "OBF_PLANE")
        self.source_combo.setEnabled(is_obf)
        self.source_combo.setCurrentIndex(
            int(np.clip(st.obf_mode_index, 0, self.source_combo.count() - 1)))

        self.cmap_combo.setCurrentIndex(0 if st.use_turbo else 1)
        self.mirror_check.setChecked(bool(cfg.mirror_display))
        self.cross_check.setChecked(bool(st.show_max))

        for w in getattr(self, "_controls", []):
            w.blockSignals(False)
        self._syncing = False

        # Elements non interactifs.
        self.hud.setVisible(bool(getattr(cfg, "show_hud", True)))
        if self._cmap_turbo_cache != bool(st.use_turbo):
            self._set_colorbar(st.use_turbo)

        self.dyn_left_label.setText(f"-{int(round(st.dyn_dB))} dB")

        self.info_labels["Tw"].setText(f"{cfg.Tw:.2f} s".replace(".", ","))
        self.info_labels["Th"].setText(f"{cfg.Th:.2f} s".replace(".", ","))
        self.info_labels["Resolution"].setText(f"{cfg.delta_f:.0f} Hz")
        self.info_labels["FPS"].setText(f"{getattr(st, 'fps', 0.0):.1f}")
        self.info_labels["Frequence"].setText(f"{st.f_center:.0f} Hz")

        maxbf = getattr(st, "last_map_max_db", None)
        maxbf_txt = "-- dB" if maxbf is None else f"{maxbf:.1f} dB".replace(".", ",")
        self.info_labels["Max BF"].setText(maxbf_txt)
        self.maxbf_value.setText(maxbf_txt)

        if info is not None:
            if not info["ready"]:
                # La progression du buffer reste dans le panneau Informations ;
                # la barre du bas garde une largeur fixe (colorbar stable).
                self.info_labels["Niveau"].setText(
                    f"Buffer {info['filled']}/{cfg.win_samp}")
                self.level_value.setText("-- dB")
            else:
                lvl_txt = f"{info['Lp_mean']:.1f} dB".replace(".", ",")
                self.info_labels["Niveau"].setText(lvl_txt)
                self.level_value.setText(lvl_txt)
            self._update_trig_pill(bool(info["bf_active"]))

        # Mode 'camera seule' -> plein ecran (applique seulement au changement).
        if self._camera_only_cache != bool(st.camera_only):
            self._apply_camera_only(bool(st.camera_only))
            self._camera_only_cache = bool(st.camera_only)

        rec = getattr(self.state, "recorder", None)
        self._update_rec_indicator(bool(rec is not None and rec.is_recording))

    # --------------------------------------------------------------
    # Controles -> etat
    # --------------------------------------------------------------
    def _on_freq(self, i):
        if self._syncing:
            return
        f = self.f_lo + i * self.f_slider_step
        self.state.f_center = float(min(max(f, self.f_lo), self.f_hi))

    def _on_dyn(self, v):
        if self._syncing:
            return
        self.state.dyn_dB = float(v)

    def _on_alpha(self, v):
        if self._syncing:
            return
        self.state.alpha_scale = float(v) / 100.0

    def _on_trig(self, v):
        if self._syncing:
            return
        self.config.level_threshold_dB = float(v)

    def _on_algo(self, idx):
        if self._syncing:
            return
        idx = int(np.clip(idx, 0, len(self.state.algorithms) - 1))
        self.state.algorithm_index = idx
        self.state.algorithm = self.state.algorithms[idx]
        # Reactivite immediate : "Source OBF" pertinente seulement en OBF.
        self.source_combo.setEnabled(self.state.algorithm == "OBF_PLANE")

    def _on_source(self, idx):
        if self._syncing:
            return
        self.state.obf_mode_index = int(
            np.clip(idx, 0, self.state.obf_n_modes - 1))

    def _on_cmap(self, idx):
        if self._syncing:
            return
        self.state.use_turbo = (idx == 0)

    def _on_mode(self, idx):
        if self._syncing:
            return
        if 0 <= idx < len(self.modes):
            m = self.modes[idx]
            # Reconfigure la fenetre glissante a chaud (le buffer se remplit a
            # nouveau ; Tw/Th/delta_f affiches se mettront a jour a la frame
            # suivante). delta_f adapte aussi la fenetre FFT d'analyse.
            self.engine.set_window(m["Tw"], m["Th"], m["delta_f"])
            # La cadence d'affichage doit suivre Th (sinon, en rapide, on
            # consomme trop peu d'audio par tick -> la file MU32 deborde,
            # get_data la vide et dort 0.1 s -> affichage en retard, FPS bas).
            self.timer.setInterval(self._timer_interval_ms())
            cfg = self.config
            lenframe = max(1, int(cfg.Fe / cfg.delta_f))
            step = max(1, lenframe - int(round(
                float(getattr(cfg, "overlap", 0.5)) * lenframe)))
            nframes = 1 + max(0, cfg.win_samp - lenframe) // step
            print(f"[INFO] Mode {m['label']} : Tw={m['Tw']} s, Th={m['Th']} s, "
                  f"delta_f={m['delta_f']} Hz -> ~{nframes} trames moyennees")

    def _evaluate_modes(self):
        """
        Desactive (grise) les modes dont le pas Th est plus court que le temps
        de calcul mesure par frame : non tenables en temps reel sur ce PC. Le
        mode le plus lent reste toujours actif (meilleur effort). Si le mode
        courant devient infaisable, on bascule vers le plus rapide tenable.
        """
        if self._proc_ms <= 0.0 or not self.modes:
            return

        model = self.mode_combo.model()
        slowest = max(range(len(self.modes)),
                      key=lambda i: self.modes[i]["Th"])

        feasible = []
        for i, m in enumerate(self.modes):
            ok = (self._proc_ms <= self.PROC_MARGIN * m["Th"] * 1000.0
                  or i == slowest)
            feasible.append(ok)
            item = model.item(i)
            if item is not None:
                item.setEnabled(ok)
                item.setToolTip("" if ok else
                                f"Trop rapide pour ce PC (~{self._proc_ms:.0f} ms/frame)")

        cur = self.mode_combo.currentIndex()
        if 0 <= cur < len(feasible) and not feasible[cur]:
            cands = [i for i, ok in enumerate(feasible) if ok]
            target = min(cands, key=lambda i: self.modes[i]["Th"])
            print(f"[WARN] Mode '{self.modes[cur]['label']}' trop rapide "
                  f"(~{self._proc_ms:.0f} ms/frame) -> bascule sur "
                  f"'{self.modes[target]['label']}'")
            self.mode_combo.setCurrentIndex(target)

        off = [m["label"] for m, ok in zip(self.modes, feasible) if not ok]
        if off:
            print(f"[INFO] Modes desactives (~{self._proc_ms:.0f} ms/frame) : "
                  f"{', '.join(off)}")

    def _on_mirror(self, checked):
        if self._syncing:
            return
        self.config.mirror_display = bool(checked)

    def _on_cross(self, checked):
        if self._syncing:
            return
        self.state.show_max = bool(checked)

    # --------------------------------------------------------------
    # Clavier (reutilise la logique existante)
    # --------------------------------------------------------------
    def _rec_fps(self):
        fps = float(getattr(self.config, "record_fps", 0.0))
        if fps <= 0.0:
            fps = max(1.0, min(30.0, float(getattr(self.state, "fps", 10.0))))
        return fps

    def _route_key(self, event):
        """
        Traite une touche de raccourci. Retourne True si elle est consommee.

        Utilise a la fois par keyPressEvent ET par le filtre d'evenements de
        l'application, pour que les raccourcis marchent meme quand un slider ou
        un combo a le focus clavier.
        """
        # Echap : sortir du plein ecran 'camera seule'.
        if event.key() == Qt.Key_Escape:
            if getattr(self.state, "camera_only", False):
                self.state.toggle_camera_only()
            return True

        txt = event.text()
        if not txt or not txt.strip():
            return False  # fleches, Tab, etc. -> laisses aux widgets

        # 'q' : quitter (comme l'ancienne interface).
        if txt == "q":
            self.close()
            return True

        # 'r' : enregistrement (dashboard complet).
        if txt == "r":
            self.state.recorder.toggle(
                self._grab_dashboard_bgr(), self.config, fps=self._rec_fps())
            return True

        # Chiffres 1..9 : selection DIRECTE de la source OBF (si algo = OBF).
        if txt.isdigit() and txt != "0":
            idx = int(txt) - 1
            if (self.state.algorithm == "OBF_PLANE"
                    and 0 <= idx < int(self.state.obf_n_modes)):
                self.state.obf_mode_index = idx
            return True

        # Reste : logique clavier partagee (p, m, a, c, w/x, +/-, t/y, ,/; ...).
        if process_keyboard_from_key(ord(txt[0]), self.config, self.state):
            self.close()
        return True

    def keyPressEvent(self, event):
        if not self._route_key(event):
            super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress and self._route_key(event):
            return True
        return super().eventFilter(obj, event)

    # --------------------------------------------------------------
    # Fermeture propre
    # --------------------------------------------------------------
    def closeEvent(self, event):
        try:
            self.timer.stop()
        except Exception:
            pass
        self.engine.close()
        super().closeEvent(event)
