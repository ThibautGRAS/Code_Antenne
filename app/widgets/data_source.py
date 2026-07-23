# -*- coding: utf-8 -*-
"""Selection de la source de donnees : dossier + menu deroulant des fichiers .dat.

Le dropdown liste les mesures .dat du dossier (0, 1, 2, ...) dans le MEME ordre que
read_info.load_validation_data (sorted glob "*.dat") -> l'index choisi = chosen_index.
"""

import os
import glob

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QPushButton, QHBoxLayout, QFileDialog,
)

# app/widgets/data_source.py -> app/widgets -> app -> racine du depot
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_RAW = os.path.join(_ROOT, "data", "data_raw")


class DataSourceWidget(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        form = QFormLayout(self)
        form.setContentsMargins(4, 4, 4, 4)

        self._folder = QLineEdit("DATA_SOURCE")
        self._folder.setToolTip("Nom du sous-dossier (sous data/data_raw) OU chemin absolu.")
        browse = QPushButton("Parcourir...")
        browse.clicked.connect(self._browse)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self._folder, 1)
        rl.addWidget(browse)
        form.addRow("Dossier", row)

        self._index = QComboBox()
        self._index.currentIndexChanged.connect(lambda *_: self.changed.emit())
        form.addRow("Mesure (.dat)", self._index)

        self._folder.editingFinished.connect(self._on_folder_edited)
        self._rescan()

    def _resolve(self):
        p = self._folder.text().strip()
        if not p:
            return None
        return p if os.path.isabs(p) else os.path.join(_DATA_RAW, p)

    def _rescan(self):
        folder = self._resolve()
        self._index.blockSignals(True)
        self._index.clear()
        files = []
        if folder and os.path.isdir(folder):
            files = sorted(glob.glob(os.path.join(folder, "*.dat")))
        if files:
            for i, f in enumerate(files):
                self._index.addItem(f"{i} : {os.path.basename(f)}")
        else:
            self._index.addItem("(aucun .dat trouve)")
        self._index.blockSignals(False)

    def _on_folder_edited(self):
        self._rescan()
        self.changed.emit()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier de donnees")
        if d:
            self._folder.setText(d)
            self._rescan()
            self.changed.emit()

    def values(self):
        return {"validation_name": self._folder.text().strip(),
                "chosen_index": max(0, self._index.currentIndex())}

    def set_values(self, d):
        if "validation_name" in d:
            self._folder.blockSignals(True)
            self._folder.setText(str(d["validation_name"]))
            self._folder.blockSignals(False)
            self._rescan()
        if "chosen_index" in d:
            idx = int(d["chosen_index"])
            if 0 <= idx < self._index.count():
                self._index.blockSignals(True)
                self._index.setCurrentIndex(idx)
                self._index.blockSignals(False)
        self.changed.emit()
