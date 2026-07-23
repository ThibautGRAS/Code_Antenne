# -*- coding: utf-8 -*-
"""Page Beamforming 3D : 3 etapes optimisees + affichage EMBARQUE + logs en bas.

- Etape 1 (sous-processus) : charge le .dat + calcule la CSM sur une PLAGE -> cache.
- Etape 2 (sous-processus) : choisit une frequence DANS la plage (filtre le cache,
  aucun recalcul de CSM) + beamforming -> cache.
- Etape 3 (IN-PROCESS) : affiche le resultat embarque dans la fenetre (matplotlib
  ou pyvista selon le parametre "Visualisation").
Changer un parametre amont re-desactive les etapes aval.
"""

import os
import tempfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QPushButton, QScrollArea,
    QLabel, QSplitter,
)

from app.widgets.form import ParamForm
from app.widgets.log_console import LogConsole
from app.widgets.result_view import ResultView
from app.runner import WorkflowRunner

_WF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workflows")
_CSM_SCRIPT = os.path.join(_WF, "csm_run.py")
_BF_SCRIPT = os.path.join(_WF, "beamforming_run.py")

# Etape 1 : donnees + PLAGE de CSM a precalculer (le plus long).
_SPEC_CSM = [
    {"key": "validation_name", "label": "Dossier de donnees", "type": "folder",
     "default": "DATA_SOURCE",
     "tip": "Nom du sous-dossier (sous data/data_raw) OU chemin absolu."},
    {"key": "chosen_index", "label": "Index de la mesure", "type": "int",
     "default": 0, "min": 0, "max": 9999},
    {"key": "fmin_bf", "label": "Plage CSM : freq min (Hz)", "type": "int",
     "default": 1000, "min": 0, "max": 100000,
     "tip": "Plage LARGE a precalculer une fois. Le beamforming choisira une "
            "frequence dedans (etape 2) sans recalculer la CSM."},
    {"key": "fmax_bf", "label": "Plage CSM : freq max (Hz)", "type": "int",
     "default": 3000, "min": 0, "max": 100000},
    {"key": "delta_f", "label": "Resolution delta_f (Hz)", "type": "int",
     "default": 100, "min": 1, "max": 10000},
    {"key": "diag_remove", "label": "Retrait diagonale CSM", "type": "bool",
     "default": True, "tip": "Applique au CALCUL de la CSM -> parametre de l'etape 1."},
]
# Etape 2 : frequence a traiter (dans la plage CSM) + methode + mesh.
_SPEC_BF = [
    {"key": "_fsel_min", "label": "Freq a traiter : min (Hz)", "type": "int",
     "default": 2000, "min": 0, "max": 100000,
     "tip": "Bande a beamformer, choisie DANS la plage CSM (etape 1). "
            "La changer relance seulement le beamforming, pas la CSM."},
    {"key": "_fsel_max", "label": "Freq a traiter : max (Hz)", "type": "int",
     "default": 2000, "min": 0, "max": 100000},
    {"key": "method", "label": "Methode", "type": "choice",
     "choices": ["bartlett", "music", "obf"], "default": "bartlett"},
    {"key": "n_sources", "label": "Nb sources (MUSIC/OBF)", "type": "int",
     "default": 3, "min": 1, "max": 32},
    {"key": "mesh_name", "label": "Mesh STL", "type": "str",
     "default": "Source_3D_centre_m.stl"},
    {"key": "factor", "label": "Echelle mesh", "type": "float",
     "default": 0.95, "decimals": 3, "min": 0.0, "max": 10.0},
    {"key": "offsetx", "label": "Offset X (m)", "type": "float",
     "default": 0.765, "decimals": 3, "min": -10.0, "max": 10.0},
    {"key": "offsety", "label": "Offset Y (m)", "type": "float",
     "default": 0.77, "decimals": 3, "min": -10.0, "max": 10.0},
    {"key": "offsetz", "label": "Offset Z (m)", "type": "float",
     "default": 0.26, "decimals": 3, "min": -10.0, "max": 10.0},
]
# Etape 3 : visu embarquee.
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

        self.form_csm.changed.connect(lambda: self._invalidate(1))
        self.form_bf.changed.connect(lambda: self._invalidate(2))
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

        self.form_csm = ParamForm(_SPEC_CSM)
        self.btn_csm = QPushButton("1 - Charger + CSM")
        self.btn_csm.setObjectName("Run")
        self.btn_csm.clicked.connect(lambda: self._launch(1))
        self.lbl_csm = QLabel()
        clay.addWidget(self._group("1. Donnees + CSM  (le plus long)",
                                   self.form_csm, self.btn_csm, self.lbl_csm))

        self.form_bf = ParamForm(_SPEC_BF)
        self.btn_bf = QPushButton("2 - Beamforming")
        self.btn_bf.setObjectName("Run")
        self.btn_bf.clicked.connect(lambda: self._launch(2))
        self.lbl_bf = QLabel()
        clay.addWidget(self._group("2. Beamforming  (reutilise la CSM)",
                                   self.form_bf, self.btn_bf, self.lbl_bf))

        self.form_plot = ParamForm(_SPEC_PLOT)
        self.btn_plot = QPushButton("3 - Afficher")
        self.btn_plot.setObjectName("Run")
        self.btn_plot.clicked.connect(self._show_result)
        self.lbl_plot = QLabel()
        clay.addWidget(self._group("3. Affichage (embarque)",
                                   self.form_plot, self.btn_plot, self.lbl_plot))
        clay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setFixedWidth(420)

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

    def _group(self, title, form, button, status):
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.addWidget(form)
        lay.addWidget(button)
        status.setStyleSheet(_MUTED)
        lay.addWidget(status)
        return box

    # -------------------------------------------------------------- logique
    def _params(self):
        p = {}
        p.update(self.form_csm.values())
        p.update(self.form_bf.values())
        p.update(self.form_plot.values())
        p.setdefault("df_band_bf", 1)
        p["_cache_dir"] = self._cache_dir
        return p

    def _launch(self, step):
        """Etapes 1 et 2 : calcul en sous-processus."""
        if self.runner.running:
            return
        script = {1: _CSM_SCRIPT, 2: _BF_SCRIPT}[step]
        msg = {1: "Etape 1 : chargement + CSM...",
               2: "Etape 2 : beamforming..."}[step]
        self._step = step
        self.log.clear()
        self.log.start(msg)
        self.runner.run(script, self._params())

    def _show_result(self):
        """Etape 3 : affichage EMBARQUE (in-process) via src.plot_beamforming."""
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
