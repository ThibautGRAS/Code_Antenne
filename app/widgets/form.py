# -*- coding: utf-8 -*-
"""Formulaire de parametres generique, construit depuis une liste de specs.

Chaque spec est un dict :
    {"key", "label", "type", "default", [choices], [tip], [min], [max], [decimals]}
type in {"int", "float", "str", "choice", "bool", "folder"}.
`values()` renvoie {key: valeur} pret a passer a Config(overrides=...).
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QHBoxLayout, QPushButton, QFileDialog,
)


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
            w = QSpinBox()
            w.setRange(int(s.get("min", 0)), int(s.get("max", 10 ** 9)))
            w.setValue(int(s["default"]))
        elif t == "float":
            w = QDoubleSpinBox()
            w.setDecimals(int(s.get("decimals", 3)))
            w.setRange(float(s.get("min", -1e9)), float(s.get("max", 1e9)))
            w.setValue(float(s["default"]))
        elif t == "choice":
            w = QComboBox()
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
        """Pour un champ 'folder' : ajoute un bouton Parcourir a cote du QLineEdit."""
        if s["type"] != "folder":
            return w
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        btn = QPushButton("Parcourir...")

        def browse():
            d = QFileDialog.getExistingDirectory(self, "Choisir le dossier de donnees")
            if d:
                w.setText(d)

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
