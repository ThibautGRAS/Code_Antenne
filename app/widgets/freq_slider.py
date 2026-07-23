# -*- coding: utf-8 -*-
"""Selecteur de frequence : slider + saisie (spinbox) synchronises, bornes ajustables."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSlider, QSpinBox


class FreqSlider(QWidget):
    changed = Signal()

    def __init__(self, minv=0, maxv=100, value=0, step=1, unit="Hz", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._step = max(1, int(step))
        self._slider = QSlider(Qt.Horizontal)
        self._slider.setFocusPolicy(Qt.StrongFocus)
        self._spin = QSpinBox()
        self._spin.setFocusPolicy(Qt.StrongFocus)
        self._spin.setSuffix(f" {unit}")
        self._spin.setFixedWidth(108)
        lay.addWidget(self._slider, 1)
        lay.addWidget(self._spin)
        self.set_bounds(minv, maxv, emit=False)
        self.set_value(value, emit=False)
        self._slider.valueChanged.connect(self._on_slider)
        self._spin.valueChanged.connect(self._on_spin)

    def _on_slider(self, v):
        if self._spin.value() != v:
            self._spin.blockSignals(True)
            self._spin.setValue(v)
            self._spin.blockSignals(False)
        self.changed.emit()

    def _on_spin(self, v):
        if self._slider.value() != v:
            self._slider.blockSignals(True)
            self._slider.setValue(v)
            self._slider.blockSignals(False)
        self.changed.emit()

    def value(self):
        return int(self._spin.value())

    def set_value(self, v, emit=True):
        v = int(round(float(v)))
        for w in (self._slider, self._spin):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)
        if emit:
            self.changed.emit()

    def set_step(self, step):
        self._step = max(1, int(step))
        self._slider.setSingleStep(self._step)
        self._spin.setSingleStep(self._step)

    def set_bounds(self, minv, maxv, emit=True):
        minv, maxv = int(minv), int(maxv)
        if maxv < minv:
            minv, maxv = maxv, minv
        if maxv == minv:
            maxv = minv + 1
        cur = self.value()
        for w in (self._slider, self._spin):
            w.blockSignals(True)
            w.setRange(minv, maxv)
            w.setSingleStep(self._step)
            w.blockSignals(False)
        self.set_value(min(max(cur, minv), maxv), emit=emit)
