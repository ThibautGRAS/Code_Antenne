# -*- coding: utf-8 -*-
"""Fenetre principale : navigation laterale + pages empilees."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QStackedWidget, QLabel, QButtonGroup,
)

from app.theme import QSS
from app.pages.beamforming_page import BeamformingPage
from app.pages.placeholder_page import PlaceholderPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AntenneMu - Poste de travail (offline)")
        self.setStyleSheet(QSS)
        self.resize(1100, 700)
        self._build()

    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- Barre laterale -----
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(220)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        title = QLabel("ANTENNEMU")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        title.setContentsMargins(0, 18, 0, 18)
        sl.addWidget(title)

        # ----- Pages -----
        self.stack = QStackedWidget()
        pages = [
            ("Beamforming 3D", BeamformingPage()),
            ("Niveaux & Puissance", PlaceholderPage(
                "Niveaux & Puissance (SPL)",
                "Workflow a brancher (equivalent de main_SPL_POWER_cube).")),
            ("Calibration", PlaceholderPage(
                "Calibration",
                "Workflow a brancher (equivalent de main_CALIB).")),
        ]

        navgroup = QButtonGroup(self)
        navgroup.setExclusive(True)
        for i, (name, page) in enumerate(pages):
            self.stack.addWidget(page)
            btn = QPushButton(name)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, idx=i: self.stack.setCurrentIndex(idx))
            navgroup.addButton(btn)
            sl.addWidget(btn)
            if i == 0:
                btn.setChecked(True)

        sl.addStretch(1)
        foot = QLabel("Offline - independant du live")
        foot.setStyleSheet("color: rgb(120,135,160); padding: 12px;")
        sl.addWidget(foot)

        root.addWidget(side)
        root.addWidget(self.stack, 1)
