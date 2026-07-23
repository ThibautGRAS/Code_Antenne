# -*- coding: utf-8 -*-
"""Petits effets d'interface : halo anime au survol (QGraphicsDropShadowEffect + animation)."""

from PySide6.QtCore import QObject, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect


class _HoverGlow(QObject):
    def __init__(self, widget, color, base, hover):
        super().__init__(widget)
        self._eff = QGraphicsDropShadowEffect(widget)
        self._eff.setColor(color)
        self._eff.setXOffset(0)
        self._eff.setYOffset(2)
        self._eff.setBlurRadius(base)
        widget.setGraphicsEffect(self._eff)
        self._base = base
        self._hover = hover
        self._anim = QPropertyAnimation(self._eff, b"blurRadius", widget)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        widget.installEventFilter(self)

    def eventFilter(self, _obj, e):
        if e.type() == QEvent.Enter:
            self._to(self._hover)
        elif e.type() == QEvent.Leave:
            self._to(self._base)
        return False

    def _to(self, value):
        self._anim.stop()
        self._anim.setEndValue(value)
        self._anim.start()


def hover_glow(widget, color=(239, 51, 70, 130), base=14, hover=30):
    """Ajoute un halo qui s'intensifie doucement au survol. Retourne l'objet (a garder)."""
    return _HoverGlow(widget, QColor(*color), base, hover)
