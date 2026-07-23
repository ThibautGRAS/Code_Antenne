# -*- coding: utf-8 -*-
"""Fenetre principale : menu (Projet / Affichage / Aide), barre laterale (marque +
navigation), barre superieure (logo CETIM + titre de page), pages empilees."""

import os
import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QStackedWidget, QLabel, QButtonGroup, QFileDialog, QMessageBox,
)

from app.theme import THEMES, QSS_DARK
from app.pages.beamforming_page import BeamformingPage
from app.pages.placeholder_page import PlaceholderPage

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGO = os.path.join(_REPO, "data", "assets", "logo-cetim.png")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AntenneMu - Poste de travail (offline)")
        self.setStyleSheet(QSS_DARK)
        self.resize(1240, 800)
        self.setMinimumSize(1000, 640)
        self._project_path = None
        self._theme_name = "Sombre"
        self._build()
        self._build_menu()

    # --------------------------------------------------------------- contenu
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._sidebar())

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._topbar())
        rl.addWidget(self.stack, 1)
        root.addWidget(right, 1)

    def _sidebar(self):
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(212)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        head = QVBoxLayout()
        head.setContentsMargins(20, 22, 18, 20)
        head.setSpacing(2)
        name = QLabel("ANTENNEMU")
        name.setObjectName("Brand")
        sub = QLabel("POSTE OFFLINE")
        sub.setObjectName("BrandSub")
        head.addWidget(name)
        head.addWidget(sub)
        sl.addLayout(head)

        self.stack = QStackedWidget()
        self._pages = [
            ("Beamforming 3D", BeamformingPage()),
            ("Niveaux & Puissance", PlaceholderPage(
                "Niveaux & Puissance (SPL)",
                "Workflow a brancher (equivalent de main_SPL_POWER_cube).")),
            ("Calibration", PlaceholderPage(
                "Calibration",
                "Workflow a brancher (equivalent de main_CALIB).")),
        ]

        self._navgroup = QButtonGroup(self)
        self._navgroup.setExclusive(True)
        for i, (nm, page) in enumerate(self._pages):
            self.stack.addWidget(page)
            btn = QPushButton(nm)
            btn.setObjectName("Nav")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, idx=i: self._go(idx))
            self._navgroup.addButton(btn)
            sl.addWidget(btn)
            if i == 0:
                btn.setChecked(True)

        sl.addStretch(1)
        return side

    def _topbar(self):
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(64)
        h = QHBoxLayout(bar)
        h.setContentsMargins(20, 8, 18, 8)
        h.setSpacing(0)

        pix = QPixmap(_LOGO)
        if not pix.isNull():
            logo = QLabel()
            logo.setObjectName("Logo")
            logo.setPixmap(pix.scaledToHeight(32, Qt.SmoothTransformation))
            h.addWidget(logo)
            h.addSpacing(16)

        tit = QVBoxLayout()
        tit.setSpacing(1)
        eb = QLabel("CAMERA ACOUSTIQUE")
        eb.setObjectName("AppEyebrow")
        self.page_title = QLabel(self._pages[0][0])
        self.page_title.setObjectName("AppTitle")
        tit.addWidget(eb)
        tit.addWidget(self.page_title)
        h.addLayout(tit)
        h.addStretch(1)

        self.lbl_project = QLabel("")
        self.lbl_project.setObjectName("TopInfo")
        h.addWidget(self.lbl_project)
        return bar

    def _go(self, idx):
        self.stack.setCurrentIndex(idx)
        self.page_title.setText(self._pages[idx][0])

    # ------------------------------------------------------------ menu
    def _build_menu(self):
        mb = self.menuBar()

        proj = mb.addMenu("Projet")
        proj.addAction("Ouvrir un projet...").triggered.connect(self._open_project)
        proj.addAction("Enregistrer le projet").triggered.connect(self._save_project)
        proj.addAction("Enregistrer sous...").triggered.connect(self._save_project_as)

        disp = mb.addMenu("Affichage")
        thememenu = disp.addMenu("Theme")
        grp = QActionGroup(self)
        grp.setExclusive(True)
        for nm in THEMES:
            a = QAction(nm, self, checkable=True)
            a.setChecked(nm == self._theme_name)
            a.triggered.connect(lambda _=False, n=nm: self.apply_theme(n))
            grp.addAction(a)
            thememenu.addAction(a)

        aide = mb.addMenu("Aide")
        aide.addAction("A propos d'AntenneMu").triggered.connect(self._about)

    def apply_theme(self, name):
        self._theme_name = name
        self.setStyleSheet(THEMES.get(name, QSS_DARK))

    def _about(self):
        QMessageBox.about(
            self, "A propos d'AntenneMu",
            "AntenneMu - Poste de travail offline\n\n"
            "Camera acoustique MU32 (32 micros) + camera.\n"
            "Beamforming 3D, niveaux & puissance, calibration.\n\n"
            "CETIM")

    # ------------------------------------------------------------ projet
    def _current_page(self):
        w = self.stack.currentWidget()
        return w if hasattr(w, "get_project") and hasattr(w, "load_project") else None

    def _set_project(self, path):
        self._project_path = path
        self.lbl_project.setText(os.path.basename(path) if path else "")
        self.setWindowTitle(f"AntenneMu - {path}" if path
                            else "AntenneMu - Poste de travail (offline)")

    def _open_project(self):
        page = self._current_page()
        if page is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un projet", "", "Projet AntenneMu (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                page.load_project(json.load(f))
            self._set_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Ouverture du projet", str(exc))

    def _save_project(self):
        if self._project_path:
            self._write_project(self._project_path)
        else:
            self._save_project_as()

    def _save_project_as(self):
        page = self._current_page()
        if page is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Enregistrer le projet", "", "Projet AntenneMu (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        self._write_project(path)

    def _write_project(self, path):
        page = self._current_page()
        if page is None:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(page.get_project(), f, ensure_ascii=False, indent=2)
            self._set_project(path)
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement du projet", str(exc))
