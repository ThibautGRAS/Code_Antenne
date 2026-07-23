# -*- coding: utf-8 -*-
"""Slider horizontal + valeur affichee, sur une plage flottante."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLabel


class LabeledSlider(QWidget):
    changed = Signal()

    def __init__(self, minv, maxv, value, decimals=0, suffix="", parent=None):
        super().__init__(parent)
        self._dec = int(decimals)
        self._scale = 10 ** self._dec
        self._suffix = suffix
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setFocusPolicy(Qt.StrongFocus)
        self._slider.setRange(int(round(minv * self._scale)), int(round(maxv * self._scale)))
        self._slider.setValue(int(round(value * self._scale)))
        self._lbl = QLabel()
        self._lbl.setFixedWidth(58)
        self._lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._slider, 1)
        lay.addWidget(self._lbl)
        self._slider.valueChanged.connect(self._on)
        self._refresh_label()

    def _on(self, _v):
        self._refresh_label()
        self.changed.emit()

    def _refresh_label(self):
        self._lbl.setText(f"{self.value():.{self._dec}f}{self._suffix}")

    def value(self):
        return self._slider.value() / self._scale

    def set_value(self, v):
        self._slider.blockSignals(True)
        self._slider.setValue(int(round(float(v) * self._scale)))
        self._slider.blockSignals(False)
        self._refresh_label()
