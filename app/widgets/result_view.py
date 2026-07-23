# -*- coding: utf-8 -*-
"""Affichage EMBARQUE du resultat, en REUTILISANT src.plot_beamforming (rendu exact).

Plutot que reimplementer le rendu (ce qui perdait le maillage reconstruit, le
centrage sur l'objet, l'OBJ...), on APPELLE plot_beamforming et on embarque sa sortie :
- matplotlib : on recupere la Figure et on l'embarque dans un FigureCanvas Qt.
  plt.show est neutralise le temps de l'appel (plot_beamforming l'appelle en interne).
- pyvista : on force plot_beamforming a construire sur un QtInteractor (pyvistaqt),
  en remplacant temporairement pv.Plotter, puis on embarque ce widget.
Les impressions de plot_beamforming (dont la coche unicode) sont capturees vers les logs
(evite aussi le crash cp1252 de la sortie standard).
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

    def render(self, bf, config):
        """Rend le resultat via plot_beamforming et l'embarque. Renvoie les logs captures."""
        mode = str(getattr(config, "visual_mode", "pyvista")).lower()
        buf = io.StringIO()
        if mode == "matplotlib":
            widget = self._render_matplotlib(bf, config, buf)
        else:
            widget = self._render_pyvista(bf, config, buf)
        self._set_widget(widget)
        return buf.getvalue()

    def _call_plot(self, bf, config):
        from src import beamforming
        return beamforming.plot_beamforming(
            cfg=config,
            SPL_values=bf["SPL_map"],
            points=bf["points"],
            coordinates_list=bf["grid_pts"],
            geo_positions=bf["geo_positions"],
            show_spheres=False,
        )

    def _render_matplotlib(self, bf, config, buf):
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
                wrapper = self._call_plot(bf, config)
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

    def _render_pyvista(self, bf, config, buf):
        import pyvista as pv
        from pyvistaqt import QtInteractor

        inter = QtInteractor(self)
        orig_plotter = pv.Plotter
        pv.Plotter = lambda *a, **k: inter  # plot_beamforming construit sur notre widget
        try:
            with contextlib.redirect_stdout(buf):
                self._call_plot(bf, config)
        finally:
            pv.Plotter = orig_plotter
        return inter
