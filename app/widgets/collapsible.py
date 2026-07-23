# -*- coding: utf-8 -*-
"""Carte repliable (accordeon) : en-tete cliquable (badge + titre) + corps masquable."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect,
)


class CollapsibleCard(QFrame):
    clicked = Signal(object)

    def __init__(self, step, title, subtitle="", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._head = QWidget()
        self._head.setObjectName("CardHead")
        self._head.setCursor(Qt.PointingHandCursor)
        hh = QHBoxLayout(self._head)
        hh.setContentsMargins(16, 12, 16, 12)
        hh.setSpacing(10)
        self._badge = QLabel(str(step))
        self._badge.setObjectName("Badge")
        self._badge.setAlignment(Qt.AlignCenter)
        tbox = QVBoxLayout()
        tbox.setSpacing(1)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        tbox.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("CardSub")
            s.setWordWrap(True)
            tbox.addWidget(s)
        self._chevron = QLabel()
        self._chevron.setObjectName("Chevron")
        hh.addWidget(self._badge, 0, Qt.AlignTop)
        hh.addLayout(tbox, 1)
        hh.addWidget(self._chevron, 0, Qt.AlignVCenter)
        outer.addWidget(self._head)

        self._bodyw = QWidget()
        self._body = QVBoxLayout(self._bodyw)
        self._body.setContentsMargins(16, 2, 16, 14)
        self._body.setSpacing(8)
        outer.addWidget(self._bodyw)

        eff = QGraphicsDropShadowEffect(self)
        eff.setBlurRadius(20)
        eff.setXOffset(0)
        eff.setYOffset(3)
        eff.setColor(QColor(0, 30, 80, 70))   # ombre navy sobre (charte)
        self.setGraphicsEffect(eff)

        self._head.mousePressEvent = self._on_click
        self.set_expanded(False)

    def _on_click(self, _e):
        self.clicked.emit(self)

    def add(self, w, stretch=0):
        self._body.addWidget(w, stretch)

    def add_layout(self, lay):
        self._body.addLayout(lay)

    def set_expanded(self, on):
        self._bodyw.setVisible(on)
        self._chevron.setText("▾" if on else "▸")  # chevron bas / droite

    def is_expanded(self):
        return self._bodyw.isVisible()
