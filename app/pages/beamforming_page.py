# -*- coding: utf-8 -*-
"""Page Beamforming 3D : 3 etapes + affichage embarque + logs en bas.

- Etape 1 (sous-processus) : charge le .dat + CSM sur une PLAGE -> cache.
- Etape 2 (sous-processus) : choisit une frequence DANS la plage (filtre le cache) +
  beamforming -> cache. Reglages mesh (scale/offsets) dans une pop-up.
- Etape 3 (in-process) : affiche le resultat embarque (matplotlib/pyvista).

La source de donnees se choisit par dossier + menu deroulant des .dat. L'etat complet
(get_project/load_project) est sauvegardable en projet .json via le menu Projet.
"""

import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QScrollArea,
    QLabel, QSplitter,
)

from app.widgets.card import Card
from app.widgets.form import ParamForm
from app.widgets.data_source import DataSourceWidget
from app.widgets.param_dialog import ParamDialog
from app.widgets.log_console import LogConsole
from app.widgets.result_view import ResultView
from app.runner import WorkflowRunner

_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WF = os.path.join(_APP, "workflows")
_CSM_SCRIPT = os.path.join(_WF, "csm_run.py")
_BF_SCRIPT = os.path.join(_WF, "beamforming_run.py")
_DATA_MESH = os.path.join(os.path.dirname(_APP), "data", "data_mesh")

# Etape 1 : plage de CSM (le plus long). La source (dossier + index) est a part.
_SPEC_CSM_FREQ = [
    {"key": "fmin_bf", "label": "Plage CSM : min (Hz)", "type": "int",
     "default": 1000, "min": 0, "max": 100000,
     "tip": "Plage LARGE a precalculer une fois ; l'etape 2 choisit une frequence dedans."},
    {"key": "fmax_bf", "label": "Plage CSM : max (Hz)", "type": "int",
     "default": 3000, "min": 0, "max": 100000},
    {"key": "delta_f", "label": "delta_f (Hz)", "type": "int",
     "default": 100, "min": 1, "max": 10000},
    {"key": "diag_remove", "label": "Retrait diagonale CSM", "type": "bool", "default": True},
]
# Etape 2 : frequence a traiter + methode + mesh (l'essentiel).
_SPEC_BF_MAIN = [
    {"key": "_fsel_min", "label": "Freq a traiter : min (Hz)", "type": "int",
     "default": 2000, "min": 0, "max": 100000,
     "tip": "Dans la plage CSM. La changer relance seulement le beamforming."},
    {"key": "_fsel_max", "label": "Freq a traiter : max (Hz)", "type": "int",
     "default": 2000, "min": 0, "max": 100000},
    {"key": "method", "label": "Methode", "type": "choice",
     "choices": ["bartlett", "music", "obf"], "default": "bartlett"},
    {"key": "n_sources", "label": "Nb sources", "type": "int", "default": 3, "min": 1, "max": 32},
    {"key": "mesh_name", "label": "Mesh STL", "type": "file", "default": "Source_3D_centre_m.stl",
     "base_dir": _DATA_MESH, "filter": "Mesh STL (*.stl)",
     "tip": "Fichier .stl (par defaut dans data/data_mesh)."},
]
# Reglages avances (pop-up) : scale + offsets.
_SPEC_ADV = [
    {"key": "factor", "label": "Echelle mesh", "type": "float",
     "default": 0.95, "decimals": 3, "min": 0.0, "max": 10.0},
    {"key": "offsetx", "label": "Offset X (m)", "type": "float",
     "default": 0.765, "decimals": 3, "min": -10.0, "max": 10.0},
    {"key": "offsety", "label": "Offset Y (m)", "type": "float",
     "default": 0.77, "decimals": 3, "min": -10.0, "max": 10.0},
    {"key": "offsetz", "label": "Offset Z (m)", "type": "float",
     "default": 0.26, "decimals": 3, "min": -10.0, "max": 10.0},
]
_SPEC_PLOT = [
    {"key": "visual_mode", "label": "Visualisation", "type": "choice",
     "choices": ["pyvista", "matplotlib"], "default": "pyvista"},
]

_OK = "color: #3DD68C; font-weight: bold;"
_TODO = "color: #F5A623; font-weight: bold;"
_MUTED = "color: #93A6C0;"


class BeamformingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = WorkflowRunner(self)
        self._tmp = tempfile.TemporaryDirectory(prefix="antennemu_bf_")
        self._cache_dir = self._tmp.name
        self._csm_ready = False
        self._bf_ready = False
        self._step = None

        self._build()

        self.data_source.changed.connect(lambda: self._invalidate(1))
        self.form_csm_freq.changed.connect(lambda: self._invalidate(1))
        self.form_bf_main.changed.connect(lambda: self._invalidate(2))
        self.form_adv.changed.connect(lambda: self._invalidate(2))
        self.runner.started.connect(self._on_started)
        self.runner.output.connect(self.log.append)
        self.runner.finished.connect(self._on_finished)
        self.log.stop_requested.connect(self._request_stop)
        self._user_stopped = False
        mw = self.form_bf_main.widget("method")
        if mw is not None:
            mw.currentTextChanged.connect(self._update_nsrc)
        self._update_nsrc()
        self._refresh()

    def _update_nsrc(self, *_):
        """Nb sources n'a de sens qu'en MUSIC/OBF -> grise en bartlett."""
        mw = self.form_bf_main.widget("method")
        nsrc = self.form_bf_main.widget("n_sources")
        if mw is not None and nsrc is not None:
            nsrc.setEnabled(mw.currentText() != "bartlett")

    # ------------------------------------------------------------------ UI
    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---------- colonne gauche : cartes d'etapes (scrollable) ----------
        controls = QWidget()
        clay = QVBoxLayout(controls)
        clay.setContentsMargins(16, 0, 12, 16)
        clay.setSpacing(14)

        # Etape 1
        self.data_source = DataSourceWidget()
        self.form_csm_freq = ParamForm(_SPEC_CSM_FREQ)
        self.btn_csm = QPushButton("Charger + calculer la CSM")
        self.btn_csm.setObjectName("Run")
        self.btn_csm.clicked.connect(lambda: self._launch(1))
        self.lbl_csm = QLabel()
        self.lbl_csm.setStyleSheet(_MUTED)
        c1 = Card(step=1, title="Donnees + CSM",
                  subtitle="Chargement du .dat + FFT (le plus long)")
        c1.add(self.data_source)
        c1.add(self.form_csm_freq)
        c1.add(self.btn_csm)
        c1.add(self.lbl_csm)
        clay.addWidget(c1)

        # Etape 2
        self.form_bf_main = ParamForm(_SPEC_BF_MAIN)
        self.form_adv = ParamForm(_SPEC_ADV)
        self._adv_dialog = ParamDialog("Reglages mesh (echelle / offsets)", self.form_adv, self)
        btn_adv = QPushButton("Reglages mesh avances...")
        btn_adv.setObjectName("Ghost")
        btn_adv.clicked.connect(self._adv_dialog.exec)
        self.btn_scene = QPushButton("Afficher la scene")
        self.btn_scene.setObjectName("Ghost")
        self.btn_scene.clicked.connect(self._show_scene)
        self.btn_bf = QPushButton("Lancer le beamforming")
        self.btn_bf.setObjectName("Run")
        self.btn_bf.clicked.connect(lambda: self._launch(2))
        self.lbl_bf = QLabel()
        self.lbl_bf.setStyleSheet(_MUTED)
        c2 = Card(step=2, title="Beamforming",
                  subtitle="Reutilise la CSM (choix de la frequence)")
        c2.add(self.form_bf_main)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(btn_adv)
        row.addWidget(self.btn_scene)
        c2.add_layout(row)
        c2.add(self.btn_bf)
        c2.add(self.lbl_bf)
        clay.addWidget(c2)

        # Etape 3
        self.form_plot = ParamForm(_SPEC_PLOT)
        self.btn_plot = QPushButton("Afficher le resultat")
        self.btn_plot.setObjectName("Run")
        self.btn_plot.clicked.connect(self._show_result)
        self.lbl_plot = QLabel()
        self.lbl_plot.setStyleSheet(_MUTED)
        c3 = Card(step=3, title="Affichage",
                  subtitle="Rendu embarque (matplotlib / pyvista)")
        c3.add(self.form_plot)
        c3.add(self.btn_plot)
        c3.add(self.lbl_plot)
        clay.addWidget(c3)
        clay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setFixedWidth(392)

        # ---------- droite : carte resultat (navbar + vue) ----------
        self.result_view = ResultView()

        self.navbar = QWidget()
        nb = QHBoxLayout(self.navbar)
        nb.setContentsMargins(0, 0, 0, 8)
        nb.setSpacing(8)
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setObjectName("Ghost")
        self.btn_prev.setFixedWidth(46)
        self.btn_prev.clicked.connect(lambda: self._nav(-1))
        self.lbl_source = QLabel("")
        self.lbl_source.setAlignment(Qt.AlignCenter)
        self.lbl_source.setStyleSheet("font-weight: 700; color: #E7EEF7;")
        self.btn_next = QPushButton("▶")
        self.btn_next.setObjectName("Ghost")
        self.btn_next.setFixedWidth(46)
        self.btn_next.clicked.connect(lambda: self._nav(1))
        nb.addWidget(self.btn_prev)
        nb.addWidget(self.lbl_source, 1)
        nb.addWidget(self.btn_next)
        self.navbar.setVisible(False)

        result_card = Card(title="Resultat", shadow=False)
        result_card.add(self.navbar)
        result_card.add(self.result_view, 1)

        top = QWidget()
        toplay = QHBoxLayout(top)
        toplay.setContentsMargins(0, 16, 16, 0)
        toplay.setSpacing(0)
        toplay.addWidget(scroll)
        toplay.addWidget(result_card, 1)

        # ---------- bas : logs ----------
        self.log = LogConsole()
        logwrap = QWidget()
        lw = QVBoxLayout(logwrap)
        lw.setContentsMargins(16, 0, 16, 14)
        lw.addWidget(self.log)

        split = QSplitter(Qt.Vertical)
        split.addWidget(top)
        split.addWidget(logwrap)
        split.setStretchFactor(0, 1)
        split.setSizes([560, 170])
        outer.addWidget(split)

    # ------------------------------------------------------ projet (get/load)
    def get_project(self):
        p = {}
        p.update(self.data_source.values())
        p.update(self.form_csm_freq.values())
        p.update(self.form_bf_main.values())
        p.update(self.form_adv.values())
        p.update(self.form_plot.values())
        return p

    def load_project(self, d):
        self.data_source.set_values(d)
        self.form_csm_freq.set_values(d)
        self.form_bf_main.set_values(d)
        self.form_adv.set_values(d)
        self.form_plot.set_values(d)

    # -------------------------------------------------------------- logique
    def _params(self):
        p = dict(self.get_project())
        p.setdefault("df_band_bf", 1)
        p["_cache_dir"] = self._cache_dir
        return p

    def _launch(self, step):
        if self.runner.running:
            return
        script = {1: _CSM_SCRIPT, 2: _BF_SCRIPT}[step]
        msg = {1: "Etape 1 : chargement + CSM...", 2: "Etape 2 : beamforming..."}[step]
        self._step = step
        self.log.clear()
        self.log.start(msg)
        self.runner.run(script, self._params())

    def _request_stop(self):
        """Tue le sous-processus de calcul (etape 1 ou 2) en cours."""
        if self.runner.running:
            self._user_stopped = True
            self.log.append("Arret demande, interruption du calcul...")
            self.runner.stop()

    def _show_result(self):
        import numpy as np
        from data.config import Config
        bf_file = os.path.join(self._cache_dir, "bf.npz")
        if not os.path.exists(bf_file):
            self.log.append("[ERREUR] Aucune carte : lance d'abord l'etape 2.")
            return
        data = np.load(bf_file)
        self._maps = np.asarray(data["SPL_maps"])          # (K, N)
        self._labels = ([str(x) for x in data["labels"]]
                        if "labels" in data.files
                        else [str(i) for i in range(len(self._maps))])
        self._points = data["points"]
        self._grid = data["grid_pts"]
        self._geo = data["geo_positions"]
        cfg_over = {k: v for k, v in self._params().items() if not k.startswith("_")}
        self._config = Config(overrides=cfg_over)
        self._n_maps = int(self._maps.shape[0])
        self._map_index = 0
        self.navbar.setVisible(self._n_maps > 1)
        self._render_current()

    def _render_current(self, preserve_view=False):
        view = self.result_view.capture_view() if preserve_view else None
        spl = self._maps[self._map_index]
        label = self._labels[self._map_index]
        self.lbl_source.setText(label if self._n_maps > 1 else "")
        self.log.start(f"Affichage ({self._config.visual_mode}) : {label}...")
        try:
            logs = self.result_view.render(
                spl, self._points, self._grid, self._geo, self._config, restore_view=view)
            if logs and logs.strip():
                self.log.append(logs)
            self.log.stop("Affichage OK.")
        except Exception:
            import traceback
            self.log.append(traceback.format_exc())
            self.log.stop("Echec de l'affichage - voir les logs.")

    def _nav(self, delta):
        if getattr(self, "_n_maps", 0) <= 1:
            return
        self._map_index = (self._map_index + delta) % self._n_maps
        self._render_current(preserve_view=True)   # garde la camera courante

    def _show_scene(self):
        """Apercu de la scene (STL + antenne) AVANT tout calcul de beamforming."""
        import io
        import contextlib
        import numpy as np
        from data.config import Config
        cfg_over = {k: v for k, v in self._params().items() if not k.startswith("_")}
        config = Config(overrides=cfg_over)
        self.log.start("Chargement de la scene (STL + antenne)...")
        buf = io.StringIO()
        try:
            from src.beamforming.beamforming_mesh import load_mesh, transform_mesh
            from src import read_info
            with contextlib.redirect_stdout(buf):
                pts_stl = load_mesh(config.file_mesh, factor_dim=1)
                points, grid = transform_mesh(
                    pts_stl, config.rotation_deg,
                    config.offsetx, config.offsety, config.offsetz)
                geo = np.asarray(read_info.load_geo_positions(config))
            self.navbar.setVisible(False)
            logs = self.result_view.render_scene(points, grid, geo, config)
            if buf.getvalue().strip():
                self.log.append(buf.getvalue())
            if logs and logs.strip():
                self.log.append(logs)
            self.log.stop("Scene affichee.")
        except Exception:
            import traceback
            if buf.getvalue().strip():
                self.log.append(buf.getvalue())
            self.log.append(traceback.format_exc())
            self.log.stop("Echec scene - voir les logs.")

    def _on_started(self):
        for b in (self.btn_csm, self.btn_bf, self.btn_plot):
            b.setEnabled(False)
        self.log.btn_stop.setEnabled(True)

    def _on_finished(self, code):
        self.log.btn_stop.setEnabled(False)
        if self._user_stopped:
            self._user_stopped = False
            self.log.stop("Calcul arrete.")
            self._refresh()
            return
        ok = (code == 0)
        if ok and self._step == 1:
            self._csm_ready = True
            self._bf_ready = False
        elif ok and self._step == 2:
            self._bf_ready = True
        self.log.stop("Termine." if ok else f"Echec (code {code}) - voir les logs.")
        self._refresh()
        if ok and self._step == 2:
            self._show_result()   # affichage automatique apres le beamforming

    def _invalidate(self, level):
        if level <= 1:
            self._csm_ready = False
            self._bf_ready = False
        elif level == 2:
            self._bf_ready = False
        self._refresh()

    def _refresh(self):
        running = self.runner.running
        self.btn_csm.setEnabled(not running)
        self.btn_bf.setEnabled(self._csm_ready and not running)
        self.btn_plot.setEnabled(self._bf_ready and not running)

        self.lbl_csm.setText("CSM prete." if self._csm_ready else "CSM a calculer.")
        self.lbl_csm.setStyleSheet(_OK if self._csm_ready else _TODO)
        if not self._csm_ready:
            self.lbl_bf.setText("Lancer d'abord l'etape 1.")
            self.lbl_bf.setStyleSheet(_MUTED)
        else:
            self.lbl_bf.setText("Beamforming pret." if self._bf_ready else "A (re)calculer.")
            self.lbl_bf.setStyleSheet(_OK if self._bf_ready else _TODO)
        if not self._bf_ready:
            self.lbl_plot.setText("Lancer d'abord l'etape 2.")
            self.lbl_plot.setStyleSheet(_MUTED)
        else:
            self.lbl_plot.setText("Pret a afficher.")
            self.lbl_plot.setStyleSheet(_OK)
