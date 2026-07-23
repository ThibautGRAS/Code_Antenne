# -*- coding: utf-8 -*-
"""Formulaire de parametres generique, construit depuis une liste de specs.

Chaque spec est un dict :
    {"key", "label", "type", "default", [choices], [tip], [min], [max], [decimals]}
type in {"int", "float", "str", "choice", "bool", "folder"}.
`values()` renvoie {key: valeur} pret a passer a Config(overrides=...).
"""

import os

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QHBoxLayout, QPushButton, QFileDialog,
)

from app.widgets.paths import last_dir, remember_dir


# --- Champs qui ne "volent" pas la molette : sans focus, on laisse defiler le panneau. ---
class _NoScrollSpinBox(QSpinBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _NoScrollDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class _NoScrollComboBox(QComboBox):
    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()


class ParamForm(QWidget):
    changed = Signal()  # emis des qu'un champ change (pour invalider les caches aval)

    def __init__(self, specs, parent=None):
        super().__init__(parent)
        self._specs = {s["key"]: s for s in specs}
        self._widgets = {}

        form = QFormLayout(self)
        form.setContentsMargins(4, 4, 4, 4)
        form.setVerticalSpacing(8)
        for s in specs:
            w = self._make_widget(s)
            self._widgets[s["key"]] = w
            form.addRow(s["label"], self._wrap(s, w))

    def _make_widget(self, s):
        t = s["type"]
        if t == "int":
            w = _NoScrollSpinBox()
            w.setFocusPolicy(Qt.StrongFocus)
            w.setRange(int(s.get("min", 0)), int(s.get("max", 10 ** 9)))
            w.setValue(int(s["default"]))
        elif t == "float":
            w = _NoScrollDoubleSpinBox()
            w.setFocusPolicy(Qt.StrongFocus)
            w.setDecimals(int(s.get("decimals", 3)))
            w.setRange(float(s.get("min", -1e9)), float(s.get("max", 1e9)))
            w.setValue(float(s["default"]))
        elif t == "choice":
            w = _NoScrollComboBox()
            w.setFocusPolicy(Qt.StrongFocus)
            w.addItems([str(c) for c in s["choices"]])
            w.setCurrentText(str(s["default"]))
        elif t == "bool":
            w = QCheckBox()
            w.setChecked(bool(s["default"]))
        else:  # "str" ou "folder"
            w = QLineEdit(str(s.get("default", "") or ""))
        if s.get("tip"):
            w.setToolTip(s["tip"])
        self._connect_change(t, w)
        return w

    def _connect_change(self, t, w):
        """Relaie tout changement de champ vers le signal `changed`."""
        if t in ("int", "float"):
            w.valueChanged.connect(self.changed)
        elif t == "choice":
            w.currentIndexChanged.connect(self.changed)
        elif t == "bool":
            w.toggled.connect(self.changed)
        else:
            w.textChanged.connect(self.changed)

    def _wrap(self, s, w):
        """Champs 'folder'/'file' : bouton Parcourir + memoire du dernier dossier."""
        t = s["type"]
        if t not in ("folder", "file"):
            return w
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("Parcourir...")
        key = s["key"]
        base_dir = s.get("base_dir")
        filt = s.get("filter", "Tous les fichiers (*.*)")

        def browse():
            start = last_dir(key) or (base_dir or "")
            if t == "folder":
                path = QFileDialog.getExistingDirectory(self, "Choisir un dossier", start)
            else:
                path, _sel = QFileDialog.getOpenFileName(self, "Choisir un fichier", start, filt)
            if not path:
                return
            remember_dir(key, path)
            # Fichier dans le dossier standard -> on stocke juste le nom (projet portable).
            if (t == "file" and base_dir
                    and os.path.normcase(os.path.dirname(path)) == os.path.normcase(base_dir)):
                w.setText(os.path.basename(path))
            else:
                w.setText(path)

        btn.clicked.connect(browse)
        lay.addWidget(w, 1)
        lay.addWidget(btn)
        return box

    def values(self):
        out = {}
        for key, w in self._widgets.items():
            t = self._specs[key]["type"]
            if t == "int":
                out[key] = int(w.value())
            elif t == "float":
                out[key] = float(w.value())
            elif t == "choice":
                out[key] = w.currentText()
            elif t == "bool":
                out[key] = bool(w.isChecked())
            else:
                out[key] = w.text()
        return out

    def set_values(self, d):
        """Restaure les champs presents dans d (ignore les cles inconnues)."""
        for key, w in self._widgets.items():
            if key not in d:
                continue
            t = self._specs[key]["type"]
            v = d[key]
            w.blockSignals(True)
            try:
                if t == "int":
                    w.setValue(int(v))
                elif t == "float":
                    w.setValue(float(v))
                elif t == "choice":
                    w.setCurrentText(str(v))
                elif t == "bool":
                    w.setChecked(bool(v))
                else:
                    w.setText("" if v is None else str(v))
            finally:
                w.blockSignals(False)
        self.changed.emit()

    def widget(self, key):
        """Acces au widget d'un champ (pour activer/desactiver depuis l'exterieur)."""
        return self._widgets.get(key)
