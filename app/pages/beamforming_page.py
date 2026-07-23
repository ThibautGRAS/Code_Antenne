# -*- coding: utf-8 -*-
"""Page Beamforming 3D (cube) : configure les parametres et lance le calcul.

Equivalent GUI de main_BEAMFORMING_cube.py. Le calcul tourne en sous-processus
(app/workflows/beamforming_run.py) ; ici on ne fait QUE construire les params et
afficher les logs.
"""

import os

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QPushButton, QScrollArea,
)

from app.widgets.form import ParamForm
from app.widgets.log_console import LogConsole
from app.runner import WorkflowRunner

# app/pages/ -> app/ -> .../app/workflows/beamforming_run.py
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_APP_DIR, "workflows", "beamforming_run.py")

# Defauts alignes sur config.yaml / le params_main de main_BEAMFORMING_cube.
_SPECS = [
    {"key": "validation_name", "label": "Dossier de donnees", "type": "folder",
     "default": "DATA_SOURCE",
     "tip": "Nom du sous-dossier (sous data/data_raw) OU chemin absolu vers les signaux."},
    {"key": "chosen_index", "label": "Index de la mesure", "type": "int",
     "default": 0, "min": 0, "max": 9999},
    {"key": "fmin_bf", "label": "Frequence min (Hz)", "type": "int",
     "default": 2000, "min": 0, "max": 100000},
    {"key": "fmax_bf", "label": "Frequence max (Hz)", "type": "int",
     "default": 2005, "min": 0, "max": 100000},
    {"key": "delta_f", "label": "Resolution delta_f (Hz)", "type": "int",
     "default": 100, "min": 1, "max": 10000},
    {"key": "method", "label": "Methode", "type": "choice",
     "choices": ["bartlett", "music", "obf"], "default": "bartlett"},
    {"key": "n_sources", "label": "Nb sources (MUSIC/OBF)", "type": "int",
     "default": 3, "min": 1, "max": 32},
    {"key": "diag_remove", "label": "Retrait diagonale CSM", "type": "bool",
     "default": True},
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
    {"key": "visual_mode", "label": "Visualisation", "type": "choice",
     "choices": ["pyvista", "matplotlib"], "default": "pyvista"},
]


class BeamformingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.runner = WorkflowRunner(self)
        self._build()
        self.runner.started.connect(lambda: self._set_running(True))
        self.runner.output.connect(self.log.append)
        self.runner.finished.connect(self._on_finished)

    def _build(self):
        root = QHBoxLayout(self)

        box = QGroupBox("Parametres")
        boxlay = QVBoxLayout(box)
        self.form = ParamForm(_SPECS)
        boxlay.addWidget(self.form)
        self.run_btn = QPushButton("Lancer le beamforming")
        self.run_btn.setObjectName("Run")
        self.run_btn.clicked.connect(self._launch)
        boxlay.addWidget(self.run_btn)
        boxlay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        scroll.setFixedWidth(380)
        root.addWidget(scroll)

        self.log = LogConsole()
        root.addWidget(self.log, 1)

    def _launch(self):
        if self.runner.running:
            return
        params = self.form.values()
        params.setdefault("df_band_bf", 1)  # champ avance laisse au defaut
        self.log.clear()
        self.log.append(f"[params] {params}")
        self.log.start("Beamforming en cours...")
        self.runner.run(_SCRIPT, params)

    def _set_running(self, running):
        self.run_btn.setEnabled(not running)

    def _on_finished(self, code):
        self._set_running(False)
        if code == 0:
            self.log.stop("Termine avec succes.")
        else:
            self.log.stop(f"Echec (code {code}) - voir les logs ci-dessus.")
