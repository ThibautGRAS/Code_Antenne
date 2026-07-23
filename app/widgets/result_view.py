# -*- coding: utf-8 -*-
"""Affichage EMBARQUE, en REUTILISANT src.plot_beamforming (rendu exact).

On appelle plot_beamforming (qui reconstruit le maillage, centre sur l'objet, gere
l'OBJ...) et on embarque sa sortie :
- matplotlib : la Figure dans un FigureCanvas Qt (plt.show neutralise) ;
- pyvista : pv.Plotter remplace temporairement par un QtInteractor (pyvistaqt).
`show_spheres=True` sert a l'apercu de scene (STL + antenne) avant calcul.
Les impressions (dont la coche unicode) sont capturees vers les logs.
"""

import io
import contextlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._current = None
        self._placeholder = QLabel("Le resultat s'affichera ici.\nLance 1 -> 2 -> 3.")
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

    def render(self, spl_values, points, grid_pts, geo_positions, config, show_spheres=False):
        """Rend UNE carte (spl_values) via plot_beamforming et l'embarque."""
        bf = {"SPL_map": spl_values, "points": points,
              "grid_pts": grid_pts, "geo_positions": geo_positions}
        mode = str(getattr(config, "visual_mode", "pyvista")).lower()
        buf = io.StringIO()
        if mode == "matplotlib":
            widget = self._render_matplotlib(bf, config, buf, show_spheres)
        else:
            widget = self._render_pyvista(bf, config, buf, show_spheres)
        self._set_widget(widget)
        return buf.getvalue()

    def _call_plot(self, bf, config, show_spheres):
        from src import beamforming
        return beamforming.plot_beamforming(
            cfg=config,
            SPL_values=bf["SPL_map"],
            points=bf["points"],
            coordinates_list=bf["grid_pts"],
            geo_positions=bf["geo_positions"],
            show_spheres=show_spheres,
        )

    def _render_matplotlib(self, bf, config, buf, show_spheres):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        try:
            from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
        except Exception:
            NavigationToolbar2QT = None

        orig_show = plt.show
        plt.show = lambda *a, **k: None  # ne pas bloquer / ouvrir de fenetre
        try:
            with contextlib.redirect_stdout(buf):
                wrapper = self._call_plot(bf, config, show_spheres)
        finally:
            plt.show = orig_show

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        canvas = FigureCanvasQTAgg(wrapper.fig)
        if NavigationToolbar2QT is not None:
            lay.addWidget(NavigationToolbar2QT(canvas, container))
        lay.addWidget(canvas, 1)
        return container

    def _render_pyvista(self, bf, config, buf, show_spheres):
        import pyvista as pv
        from pyvistaqt import QtInteractor

        inter = QtInteractor(self)
        orig_plotter = pv.Plotter
        pv.Plotter = lambda *a, **k: inter  # plot_beamforming construit dans notre widget
        try:
            with contextlib.redirect_stdout(buf):
                self._call_plot(bf, config, show_spheres)
        finally:
            pv.Plotter = orig_plotter
        return inter
