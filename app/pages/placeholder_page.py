# -*- coding: utf-8 -*-
"""Page 'a venir' pour les workflows pas encore branches."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlaceholderPage(QWidget):
    def __init__(self, title, note="", parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignCenter)

        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size: 20px; font-weight: bold;")

        n = QLabel(note or "A brancher dans une prochaine etape.")
        n.setAlignment(Qt.AlignCenter)
        n.setStyleSheet("color: rgb(150,165,185);")

        lay.addWidget(t)
        lay.addWidget(n)
