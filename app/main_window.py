# -*- coding: utf-8 -*-
"""Fenetre principale : barre laterale (marque + navigation), barre superieure
(eyebrow + titre de page + actions Projet), pages empilees."""

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QStackedWidget, QLabel, QButtonGroup, QFileDialog, QMessageBox,
)

from app.theme import QSS
from app.pages.beamforming_page import BeamformingPage
from app.pages.placeholder_page import PlaceholderPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AntenneMu - Poste de travail (offline)")
        self.setStyleSheet(QSS)
        self.resize(1240, 780)
        self.setMinimumSize(1000, 640)
        self._project_path = None
        self._build()

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

        brand = QWidget()
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(20, 22, 18, 20)
        bl.setSpacing(2)
        name = QLabel("ANTENNEMU")
        name.setObjectName("Brand")
        sub = QLabel("POSTE OFFLINE")
        sub.setObjectName("BrandSub")
        bl.addWidget(name)
        bl.addWidget(sub)
        sl.addWidget(brand)

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
        bar.setFixedHeight(60)
        h = QHBoxLayout(bar)
        h.setContentsMargins(22, 8, 16, 8)
        h.setSpacing(0)

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

        b_open = QPushButton("Ouvrir")
        b_open.setObjectName("Ghost")
        b_open.clicked.connect(self._open_project)
        b_save = QPushButton("Enregistrer")
        b_save.clicked.connect(self._save_project)
        h.addSpacing(14)
        h.addWidget(b_open)
        h.addSpacing(8)
        h.addWidget(b_save)
        return bar

    def _go(self, idx):
        self.stack.setCurrentIndex(idx)
        self.page_title.setText(self._pages[idx][0])

    # ------------------------------------------------------------ projet
    def _current_page(self):
        w = self.stack.currentWidget()
        return w if hasattr(w, "get_project") and hasattr(w, "load_project") else None

    def _set_project(self, path):
        self._project_path = path
        import os
        self.lbl_project.setText(os.path.basename(path) if path else "")
        self.setWindowTitle(f"AntenneMu - {path}" if path else "AntenneMu - Poste de travail (offline)")

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
