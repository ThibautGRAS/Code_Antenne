# -*- coding: utf-8 -*-
"""Fenetre principale : menu Projet + navigation laterale + pages empilees."""

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
        self.resize(1180, 720)
        self._project_path = None
        self._build_menu()
        self._build()

    # ------------------------------------------------------------ menu Projet
    def _build_menu(self):
        m = self.menuBar().addMenu("Projet")
        m.addAction("Ouvrir un projet...").triggered.connect(self._open_project)
        m.addAction("Enregistrer le projet").triggered.connect(self._save_project)
        m.addAction("Enregistrer sous...").triggered.connect(self._save_project_as)

    def _current_page(self):
        w = self.stack.currentWidget()
        return w if hasattr(w, "get_project") and hasattr(w, "load_project") else None

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
            self._project_path = path
            self.setWindowTitle(f"AntenneMu - {path}")
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
            self._project_path = path
            self.setWindowTitle(f"AntenneMu - {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Enregistrement du projet", str(exc))

    # ------------------------------------------------------------ contenu
    def _build(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        title = QLabel("ANTENNEMU")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignCenter)
        title.setContentsMargins(0, 18, 0, 18)
        sl.addWidget(title)

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
