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
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QLabel, QSplitter,
)

from app.widgets.form import ParamForm
from app.widgets.data_source import DataSourceWidget
from app.widgets.param_dialog import ParamDialog
from app.widgets.log_console import LogConsole
from app.widgets.result_view import ResultView
from app.runner import WorkflowRunner

_WF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workflows")
_CSM_SCRIPT = os.path.join(_WF, "csm_run.py")
_BF_SCRIPT = os.path.join(_WF, "beamforming_run.py")

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
    {"key": "mesh_name", "label": "Mesh STL", "type": "str", "default": "Source_3D_centre_m.stl"},
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

_OK = "color: rgb(90,200,120);"
_TODO = "color: rgb(230,180,80);"
_MUTED = "color: rgb(150,165,185);"


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
        self._refresh()

    # ------------------------------------------------------------------ UI
    def _build(self):
        outer = QVBoxLayout(self)

        controls = QWidget()
        clay = QVBoxLayout(controls)
        clay.setContentsMargins(0, 0, 0, 0)

        # --- Etape 1 ---
        self.data_source = DataSourceWidget()
        self.form_csm_freq = ParamForm(_SPEC_CSM_FREQ)
        self.btn_csm = QPushButton("1 - Charger + CSM")
        self.btn_csm.setObjectName("Run")
        self.btn_csm.clicked.connect(lambda: self._launch(1))
        self.lbl_csm = QLabel()
        g1 = QGroupBox("1. Donnees + CSM  (le plus long)")
        g1l = QVBoxLayout(g1)
        g1l.addWidget(self.data_source)
        g1l.addWidget(self.form_csm_freq)
        g1l.addWidget(self.btn_csm)
        self.lbl_csm.setStyleSheet(_MUTED)
        g1l.addWidget(self.lbl_csm)
        clay.addWidget(g1)

        # --- Etape 2 ---
        self.form_bf_main = ParamForm(_SPEC_BF_MAIN)
        self.form_adv = ParamForm(_SPEC_ADV)
        self._adv_dialog = ParamDialog("Reglages mesh (echelle / offsets)", self.form_adv, self)
        btn_adv = QPushButton("Reglages mesh avances...")
        btn_adv.clicked.connect(self._adv_dialog.exec)
        self.btn_bf = QPushButton("2 - Beamforming")
        self.btn_bf.setObjectName("Run")
        self.btn_bf.clicked.connect(lambda: self._launch(2))
        self.lbl_bf = QLabel()
        g2 = QGroupBox("2. Beamforming  (reutilise la CSM)")
        g2l = QVBoxLayout(g2)
        g2l.addWidget(self.form_bf_main)
        g2l.addWidget(btn_adv)
        g2l.addWidget(self.btn_bf)
        self.lbl_bf.setStyleSheet(_MUTED)
        g2l.addWidget(self.lbl_bf)
        clay.addWidget(g2)

        # --- Etape 3 ---
        self.form_plot = ParamForm(_SPEC_PLOT)
        self.btn_plot = QPushButton("3 - Afficher")
        self.btn_plot.setObjectName("Run")
        self.btn_plot.clicked.connect(self._show_result)
        self.lbl_plot = QLabel()
        g3 = QGroupBox("3. Affichage (embarque)")
        g3l = QVBoxLayout(g3)
        g3l.addWidget(self.form_plot)
        g3l.addWidget(self.btn_plot)
        self.lbl_plot.setStyleSheet(_MUTED)
        g3l.addWidget(self.lbl_plot)
        clay.addWidget(g3)
        clay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setFixedWidth(400)

        self.result_view = ResultView()

        top = QWidget()
        toplay = QHBoxLayout(top)
        toplay.setContentsMargins(0, 0, 0, 0)
        toplay.addWidget(scroll)
        toplay.addWidget(self.result_view, 1)

        self.log = LogConsole()

        split = QSplitter(Qt.Vertical)
        split.addWidget(top)
        split.addWidget(self.log)
        split.setStretchFactor(0, 1)
        split.setSizes([520, 180])
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

    def _show_result(self):
        import numpy as np
        from data.config import Config
        bf_file = os.path.join(self._cache_dir, "bf.npz")
        if not os.path.exists(bf_file):
            self.log.append("[ERREUR] Aucune carte : lance d'abord l'etape 2.")
            return
        data = np.load(bf_file)
        bf = {k: data[k] for k in data.files}
        cfg_over = {k: v for k, v in self._params().items() if not k.startswith("_")}
        config = Config(overrides=cfg_over)
        mode = str(getattr(config, "visual_mode", "pyvista"))
        self.log.start(f"Affichage embarque ({mode})...")
        try:
            logs = self.result_view.render(bf, config)
            if logs and logs.strip():
                self.log.append(logs)
            self.log.stop("Affichage OK.")
        except Exception:
            import traceback
            self.log.append(traceback.format_exc())
            self.log.stop("Echec de l'affichage - voir les logs.")

    def _on_started(self):
        for b in (self.btn_csm, self.btn_bf, self.btn_plot):
            b.setEnabled(False)

    def _on_finished(self, code):
        ok = (code == 0)
        if ok and self._step == 1:
            self._csm_ready = True
            self._bf_ready = False
        elif ok and self._step == 2:
            self._bf_ready = True
        self.log.stop("Termine." if ok else f"Echec (code {code}) - voir les logs.")
        self._refresh()

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
