# -*- coding: utf-8 -*-
"""Zone d'affichage EMBARQUEE du resultat de beamforming (matplotlib OU pyvista).

Rendu in-process dans le GUI (les widgets vivent dans l'app). Les libs de visu sont
importees a la demande (l'app demarre sans les charger). On affiche un nuage de
points du maillage colore par le niveau (dB) + les micros -- une representation
embarquee des memes donnees que la carte offline.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._current = None
        self._placeholder = QLabel(
            "Le resultat s'affichera ici.\nLance 1 -> 2 -> 3.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color: rgb(150,165,185);")
        self._lay.addWidget(self._placeholder)

    def _set_widget(self, w):
        if self._current is not None:
            self._current.setParent(None)
            self._current.deleteLater()
        self._placeholder.setVisible(False)
        self._current = w
        self._lay.addWidget(w)

    # ---- matplotlib (3D scatter) : aucune dependance en plus, testable ----
    def show_matplotlib(self, bf):
        import numpy as np
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        try:
            from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
        except Exception:
            NavigationToolbar2QT = None

        grid = np.asarray(bf["grid_pts"], dtype=float)
        spl = np.asarray(bf["SPL_map"], dtype=float).ravel()
        geo = np.asarray(bf["geo_positions"], dtype=float)

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)

        fig = Figure(figsize=(5, 4))
        ax = fig.add_subplot(111, projection="3d")
        sc = ax.scatter(grid[:, 0], grid[:, 1], grid[:, 2], c=spl, cmap="jet", s=6)
        if geo.size:
            ax.scatter(geo[:, 0], geo[:, 1], geo[:, 2], c="black", marker="^", s=14)
        fig.colorbar(sc, ax=ax, shrink=0.6, label="dB")
        ax.set_title("Beamforming (dB)")

        canvas = FigureCanvasQTAgg(fig)
        if NavigationToolbar2QT is not None:
            lay.addWidget(NavigationToolbar2QT(canvas, container))
        lay.addWidget(canvas, 1)
        self._set_widget(container)

    # ---- pyvista (QtInteractor) : necessite pyvistaqt ----
    def show_pyvista(self, bf):
        import numpy as np
        import pyvista as pv
        from pyvistaqt import QtInteractor

        grid = np.asarray(bf["grid_pts"], dtype=float)
        spl = np.asarray(bf["SPL_map"], dtype=float).ravel()
        geo = np.asarray(bf["geo_positions"], dtype=float)

        inter = QtInteractor(self)
        cloud = pv.PolyData(grid)
        cloud["dB"] = spl
        inter.add_mesh(cloud, scalars="dB", cmap="jet", point_size=8,
                       render_points_as_spheres=True)
        if geo.size:
            inter.add_mesh(pv.PolyData(geo), color="white", point_size=6,
                           render_points_as_spheres=True)
        inter.add_scalar_bar(title="dB")
        inter.reset_camera()
        self._set_widget(inter)
