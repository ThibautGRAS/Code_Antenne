# -*- coding: utf-8 -*-
"""Fenetre principale : menu (Projet / Affichage / Aide), barre laterale (marque +
navigation), barre superieure (logo CETIM + titre de page), pages empilees."""

import os
import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QAction, QActionGroup, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QStackedWidget, QLabel, QButtonGroup, QFileDialog, QMessageBox,
    QGraphicsDropShadowEffect,
)

from app.theme import THEMES, QSS_DARK
from app.view_settings import VIEW, CMAPS
from app.pages.beamforming_page import BeamformingPage
from app.pages.placeholder_page import PlaceholderPage

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGO = os.path.join(_REPO, "data", "assets", "logo-cetim.png")

_GUIDE_HTML = """
<div style="color:#E7EEF7;">
<h2 style="color:#EF3346; margin:0 0 2px 0;">Imagerie 3D &middot; Antenne acoustique</h2>
<p style="color:#93A6C0; margin-top:0;">Poste offline &mdash; beamforming sur mesure MU32.</p>
<p>Le traitement se fait en 3 &eacute;tapes (panneau de gauche, en accord&eacute;on).</p>

<h3 style="color:#EF3346;">1 &middot; Donn&eacute;es + CSM</h3>
<ul>
<li>Choisir le <b>dossier</b> puis le fichier <b>.dat</b> de mesure.</li>
<li>R&eacute;gler la <b>plage CSM</b> (min/max) et le <b>delta_f</b> : plage <i>large</i>
calcul&eacute;e une seule fois (&eacute;tape la plus longue).</li>
<li>Cliquer <b>Charger + calculer la CSM</b>.</li>
</ul>

<h3 style="color:#EF3346;">2 &middot; Beamforming</h3>
<ul>
<li><b>Bande de fr&eacute;quence</b> : glisser les deux poign&eacute;es (ou saisir min/max),
born&eacute;e &agrave; la plage CSM. La changer <b>ne recalcule pas</b> la CSM.</li>
<li><b>M&eacute;thode</b> : bartlett / music / obf ; en OBF r&eacute;gler le <b>nombre de sources</b>.</li>
<li><b>Mesh STL</b> + <i>R&eacute;glages mesh avanc&eacute;s</i> (&eacute;chelle / offsets).</li>
<li><b>Afficher la sc&egrave;ne</b> : aper&ccedil;u objet + antenne avant calcul.</li>
<li>Cliquer <b>Lancer le beamforming</b>.</li>
</ul>

<h3 style="color:#EF3346;">3 &middot; Affichage</h3>
<ul>
<li>Le r&eacute;sultat s'affiche automatiquement (rendu 3D pyvista).</li>
<li><b>Vue de la cam&eacute;ra</b> : Haut / Face / Gauche / Droite / Iso.</li>
<li>En <b>OBF</b>, les fl&egrave;ches naviguent entre les sources <b>sans recalcul</b>
(la vue est conserv&eacute;e).</li>
</ul>

<h3 style="color:#FFFFFF;">Divers</h3>
<ul>
<li><b>Arr&ecirc;ter</b> (barre du bas) interrompt un calcul en cours.</li>
<li>Menu <b>Projet</b> : enregistrer / recharger tous les r&eacute;glages (.json).</li>
<li>Menu <b>Affichage</b> : th&egrave;me clair / sombre.</li>
</ul>
</div>
"""


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

        # En-tete : logo CETIM sur plaque blanche, zone delimitee (bordure basse)
        head = QFrame()
        head.setObjectName("SideHead")
        head.setFixedHeight(70)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(14, 12, 14, 12)
        logo = QLabel()
        logo.setObjectName("Logo")
        pix = QPixmap(_LOGO)
        if not pix.isNull():
            logo.setPixmap(pix.scaledToWidth(168, Qt.SmoothTransformation))  # lockup large -> largeur
        hl.addWidget(logo)
        sl.addWidget(head)

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
        bar.setFixedHeight(70)
        h = QHBoxLayout(bar)
        h.setContentsMargins(26, 8, 20, 8)
        h.setSpacing(0)

        tit = QVBoxLayout()
        tit.setSpacing(2)
        title = QLabel("Imagerie 3D · Antenne acoustique")
        title.setObjectName("AppTitle")
        self.page_eyebrow = QLabel(self._pages[0][0])
        self.page_eyebrow.setObjectName("AppSub")
        tit.addWidget(title)
        tit.addWidget(self.page_eyebrow)
        h.addLayout(tit)
        h.addStretch(1)

        self.lbl_project = QLabel("")
        self.lbl_project.setObjectName("TopInfo")
        h.addWidget(self.lbl_project)

        eff = QGraphicsDropShadowEffect(bar)   # ombre navy sobre sous le bandeau
        eff.setBlurRadius(16)
        eff.setXOffset(0)
        eff.setYOffset(2)
        eff.setColor(QColor(0, 30, 80, 80))
        bar.setGraphicsEffect(eff)
        return bar

    def _go(self, idx):
        self.stack.setCurrentIndex(idx)
        self.page_eyebrow.setText(self._pages[idx][0])

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

        disp.addSeparator()
        cmapmenu = disp.addMenu("Palette (carte SPL)")
        cg = QActionGroup(self)
        cg.setExclusive(True)
        for cm in CMAPS:
            a = QAction(cm, self, checkable=True)
            a.setChecked(cm == VIEW.cmap)
            a.triggered.connect(lambda _=False, c=cm: self._set_cmap(c))
            cg.addAction(a)
            cmapmenu.addAction(a)

        disp.addSeparator()
        for label, attr in [("Occlusion ambiante (SSAO)", "ssao"),
                            ("Materiau satine (PBR)", "pbr"),
                            ("Halo sur le point chaud", "halo")]:
            a = QAction(label, self, checkable=True)
            a.setChecked(getattr(VIEW, attr))
            a.toggled.connect(lambda on, k=attr: self._set_effect(k, on))
            disp.addAction(a)

        aide = mb.addMenu("Aide")
        aide.addAction("Guide d'utilisation").triggered.connect(self._guide)
        aide.addSeparator()
        aide.addAction("A propos d'AntenneMu").triggered.connect(self._about)

    def apply_theme(self, name):
        self._theme_name = name
        self.setStyleSheet(THEMES.get(name, QSS_DARK))
        VIEW.set_theme(name)   # le fond du rendu 3D suit le theme (clair/sombre)
        self._rerender()

    def _set_cmap(self, cm):
        VIEW.cmap = cm
        self._rerender()

    def _set_effect(self, attr, on):
        setattr(VIEW, attr, bool(on))
        self._rerender()

    def _rerender(self):
        page = self.stack.currentWidget()
        if hasattr(page, "refresh_view"):
            page.refresh_view()

    def _guide(self):
        from PySide6.QtWidgets import QDialog, QTextBrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("Guide d'utilisation")
        dlg.resize(600, 560)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(False)
        tb.setHtml(_GUIDE_HTML)
        lay.addWidget(tb, 1)
        btn = QPushButton("Fermer")
        btn.setObjectName("Run")
        btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(btn)
        lay.addLayout(row)
        dlg.exec()

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
