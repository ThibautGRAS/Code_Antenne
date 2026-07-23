# -*- coding: utf-8 -*-
"""Carte moderne : surface blanche, coins doux, ombre teintee navy, en-tete optionnel
(badge numerote + titre + sous-titre)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QGraphicsDropShadowEffect,
)


class Card(QFrame):
    def __init__(self, step=None, title="", subtitle="", shadow=True, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(10)

        if step is not None or title:
            header = QHBoxLayout()
            header.setSpacing(10)
            if step is not None:
                badge = QLabel(str(step))
                badge.setObjectName("Badge")
                badge.setAlignment(Qt.AlignCenter)
                header.addWidget(badge, 0, Qt.AlignTop)
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
            header.addLayout(tbox, 1)
            outer.addLayout(header)

        self._body = QVBoxLayout()
        self._body.setSpacing(8)
        outer.addLayout(self._body, 1)

        if shadow:
            eff = QGraphicsDropShadowEffect(self)
            eff.setBlurRadius(26)
            eff.setXOffset(0)
            eff.setYOffset(4)
            eff.setColor(QColor(0, 0, 0, 120))
            self.setGraphicsEffect(eff)

    def add(self, w, stretch=0):
        self._body.addWidget(w, stretch)

    def add_layout(self, lay):
        self._body.addLayout(lay)
