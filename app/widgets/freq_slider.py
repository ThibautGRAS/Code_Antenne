# -*- coding: utf-8 -*-
"""Selecteur de BANDE de frequence : slider a deux poignees (peint) + deux saisies min/max."""

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSizePolicy,
)

_TRACK = "#46608A"
_FILL = "#EF3346"
_HANDLE = "#FFFFFF"


class RangeSlider(QWidget):
    """Slider horizontal a deux poignees (bande [low, high])."""
    changed = Signal()

    def __init__(self, minimum=0, maximum=100, low=0, high=100, parent=None):
        super().__init__(parent)
        self._min = int(minimum)
        self._max = int(maximum)
        self._low = int(low)
        self._high = int(high)
        self._r = 8
        self._active = None
        self.setMinimumHeight(26)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    # --- mapping valeur <-> pixel ---
    def _span(self):
        return max(1, self.width() - 2 * self._r)

    def _x(self, v):
        if self._max == self._min:
            return self._r
        return self._r + (v - self._min) / (self._max - self._min) * self._span()

    def _v(self, x):
        t = (x - self._r) / self._span()
        return int(round(self._min + t * (self._max - self._min)))

    # --- rendu ---
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        cy = self.height() / 2
        xlo, xhi = self._x(self._low), self._x(self._high)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(_TRACK))
        p.drawRoundedRect(QRectF(self._r, cy - 2, self._span(), 4), 2, 2)
        p.setBrush(QColor(_FILL))
        p.drawRoundedRect(QRectF(xlo, cy - 2.5, xhi - xlo, 5), 2, 2)
        p.setBrush(QColor(_HANDLE))
        p.setPen(QPen(QColor(_FILL), 2))
        for x in (xlo, xhi):
            p.drawEllipse(QRectF(x - self._r, cy - self._r, 2 * self._r, 2 * self._r))

    # --- souris ---
    def _pos_x(self, e):
        try:
            return e.position().x()
        except AttributeError:
            return e.x()

    def mousePressEvent(self, e):
        x = self._pos_x(e)
        self._active = "low" if abs(x - self._x(self._low)) <= abs(x - self._x(self._high)) else "high"
        self._set_from_x(x)

    def mouseMoveEvent(self, e):
        if self._active:
            self._set_from_x(self._pos_x(e))

    def mouseReleaseEvent(self, _e):
        self._active = None

    def _set_from_x(self, x):
        v = max(self._min, min(self._max, self._v(x)))
        if self._active == "low":
            v = min(v, self._high)
            if v != self._low:
                self._low = v
                self.update()
                self.changed.emit()
        elif self._active == "high":
            v = max(v, self._low)
            if v != self._high:
                self._high = v
                self.update()
                self.changed.emit()

    # --- API ---
    def low(self):
        return self._low

    def high(self):
        return self._high

    def setLow(self, v):
        self._low = max(self._min, min(int(v), self._high))
        self.update()

    def setHigh(self, v):
        self._high = min(self._max, max(int(v), self._low))
        self.update()

    def setRange(self, mn, mx):
        self._min, self._max = int(mn), int(mx)
        self._low = max(self._min, min(self._low, self._max))
        self._high = max(self._min, min(self._high, self._max))
        self.update()


class FreqBand(QWidget):
    """Bande de frequence : RangeSlider + saisies min / max (Hz), synchronises."""
    changed = Signal()

    def __init__(self, minv=0, maxv=100, low=0, high=100, step=1, parent=None):
        super().__init__(parent)
        self._step = max(1, int(step))
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        self._slider = RangeSlider(minv, maxv, low, high)
        self._lo = QSpinBox()
        self._hi = QSpinBox()
        for s, val in ((self._lo, low), (self._hi, high)):
            s.setSuffix(" Hz")
            s.setFocusPolicy(Qt.StrongFocus)
            s.setFixedWidth(112)
            s.setRange(minv, maxv)
            s.setSingleStep(self._step)
            s.setValue(val)

        row = QHBoxLayout()
        row.setSpacing(6)
        lmin = QLabel("min")
        lmin.setStyleSheet("color:#93A6C0;")
        lmax = QLabel("max")
        lmax.setStyleSheet("color:#93A6C0;")
        row.addWidget(lmin)
        row.addWidget(self._lo)
        row.addStretch(1)
        row.addWidget(lmax)
        row.addWidget(self._hi)

        v.addWidget(self._slider)
        v.addLayout(row)

        self._slider.changed.connect(self._from_slider)
        self._lo.valueChanged.connect(self._on_lo)
        self._hi.valueChanged.connect(self._on_hi)

    def _on_lo(self, val):
        if val > self._hi.value():
            self._hi.blockSignals(True)
            self._hi.setValue(val)
            self._hi.blockSignals(False)
        self._slider.setLow(val)
        self._slider.setHigh(self._hi.value())
        self.changed.emit()

    def _on_hi(self, val):
        if val < self._lo.value():
            self._lo.blockSignals(True)
            self._lo.setValue(val)
            self._lo.blockSignals(False)
        self._slider.setLow(self._lo.value())
        self._slider.setHigh(val)
        self.changed.emit()

    def _from_slider(self):
        for s, val in ((self._lo, self._slider.low()), (self._hi, self._slider.high())):
            if s.value() != val:
                s.blockSignals(True)
                s.setValue(val)
                s.blockSignals(False)
        self.changed.emit()

    # --- API (utilisee par la page) ---
    def low(self):
        return int(self._lo.value())

    def high(self):
        return int(self._hi.value())

    def set_values(self, lo, hi, emit=True):
        lo, hi = int(lo), int(hi)
        if hi < lo:
            lo, hi = hi, lo
        for s, val in ((self._lo, lo), (self._hi, hi)):
            s.blockSignals(True)
            s.setValue(val)
            s.blockSignals(False)
        self._slider.setLow(lo)
        self._slider.setHigh(hi)
        if emit:
            self.changed.emit()

    def set_step(self, step):
        self._step = max(1, int(step))
        self._lo.setSingleStep(self._step)
        self._hi.setSingleStep(self._step)

    def set_bounds(self, mn, mx, emit=True):
        mn, mx = int(mn), int(mx)
        if mx <= mn:
            mx = mn + 1
        for s in (self._lo, self._hi):
            s.blockSignals(True)
            s.setRange(mn, mx)
            s.setSingleStep(self._step)
            s.blockSignals(False)
        lo = max(mn, min(self._lo.value(), mx))
        hi = max(mn, min(self._hi.value(), mx))
        self.set_values(lo, hi, emit=emit)
