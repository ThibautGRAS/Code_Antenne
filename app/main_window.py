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

APP_VERSION = "1.0.0"

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOGO = os.path.join(_REPO, "data", "assets", "logo-cetim.png")
_ASSETS_APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
# Logo produit "Cubeam 3D" : SVG (net) prioritaire, sinon PNG.
_CUBEAM_CANDIDATES = [
    os.path.join(_ASSETS_APP, "Cubeam3D_logo_corrige_v2.svg"),
    os.path.join(_ASSETS_APP, "Cubeam3D_logo_corrige_sous_titre_v2.svg"),
    os.path.join(_ASSETS_APP, "logo.png"),
    os.path.join(_ASSETS_APP, "cubeam3d.png"),
    os.path.join(_REPO, "data", "assets", "cubeam3d.png"),
]


def _logo_pixmap(path, height, white=False):
    """Charge un logo. SVG rendu net a la hauteur voulue ; si white=True, le navy #071D45
    (texte/aretes du Cubeam) est passe en blanc pour le theme sombre (accents conserves)."""
    if path.lower().endswith(".svg"):
        try:
            from PySide6.QtSvg import QSvgRenderer
            from PySide6.QtGui import QPainter
            from PySide6.QtCore import QByteArray
            with open(path, "r", encoding="utf-8") as fh:
                data = fh.read()
            if white:
                data = data.replace("#071D45", "#FFFFFF")   # navy -> blanc (bleu/rouge gardes)
            r = QSvgRenderer(QByteArray(data.encode("utf-8")))
            if not r.isValid():
                return None
            ds = r.defaultSize()
            w = int(height * ds.width() / ds.height()) if ds.height() > 0 else height * 4
            pm = QPixmap(max(1, w), int(height))
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            r.render(p)
            p.end()
            return pm
        except Exception:
            return None
    pm = QPixmap(path)
    return None if pm.isNull() else pm.scaledToHeight(int(height), Qt.SmoothTransformation)

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
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        sl.addSpacing(16)   # (logo CETIM retire : sidebar = navigation seule)

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
        ver = QLabel(f"Cubeam 3D  ·  v{APP_VERSION}")
        ver.setObjectName("Version")
        sl.addWidget(ver)
        return side

    def _topbar(self):
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(86)
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

        # Logo produit "Cubeam 3D" en haut a droite (si le fichier est present)
        # Logo "Cubeam 3D" theme-aware : couleur en clair, blanc en sombre (sans plaque).
        self._cubeam_path = next((p for p in _CUBEAM_CANDIDATES if os.path.exists(p)), None)
        self._cubeam_logo = None
        if self._cubeam_path:
            clogo = QLabel()
            clogo.setObjectName("Logo2")
            self._cubeam_logo = clogo
            h.addSpacing(16)
            h.addWidget(clogo)
            self._refresh_cubeam()

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

    def _refresh_cubeam(self):
        """Logo Cubeam : version blanche en theme sombre, couleur en clair."""
        if not getattr(self, "_cubeam_logo", None) or not self._cubeam_path:
            return
        white = (self._theme_name != "Clair")
        pm = _logo_pixmap(self._cubeam_path, 64, white=white)
        if pm is not None and not pm.isNull():
            self._cubeam_logo.setPixmap(pm)

    def apply_theme(self, name):
        self._theme_name = name
        self.setStyleSheet(THEMES.get(name, QSS_DARK))
        VIEW.set_theme(name)   # le fond du rendu 3D suit le theme (clair/sombre)
        self._refresh_cubeam()  # logo couleur (clair) / blanc (sombre)
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
