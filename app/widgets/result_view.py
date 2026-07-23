# -*- coding: utf-8 -*-
"""Affichage 3D embarque (pyvista).

- render()       : carte de beamforming (SPL) -> REUTILISE src.plot_beamforming (rendu exact).
- render_scene() : apercu geometrie (STL + antenne) -> rendu PROPRE dedie, SANS colorbar,
                   objet en gris cadre en grand, micros en petits points rouges.
- set_view()     : oriente la camera (haut / face / gauche / droite / iso).
- capture_view()/restore : conserve la camera entre deux rendus (navigation OBF).
"""

import io
import contextlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

# Charte
_MESH = "#C1C7C6"     # gris froid (objet)
_MIC = "#EF3346"      # rouge (micros)
_BG = "#FFFFFF"


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._current = None
        self._pv = None        # QtInteractor courant
        self._placeholder = QLabel("Le resultat s'affichera ici.\nLance 1 -> 2 -> 3.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet("color: #8A9199;")
        self._lay.addWidget(self._placeholder)

    def _set_widget(self, w):
        if self._current is not None:
            self._current.setParent(None)
            self._current.deleteLater()
        self._placeholder.setVisible(False)
        self._current = w
        self._lay.addWidget(w)

    # ------------------------------------------------ camera
    def capture_view(self):
        try:
            if self._pv is not None:
                return self._pv.camera_position
        except Exception:
            pass
        return None

    def _apply_view(self, cam):
        if cam is None or self._pv is None:
            return
        try:
            self._pv.camera_position = cam
        except Exception:
            pass

    def set_view(self, name):
        """Oriente la camera sur une vue standard (pyvista)."""
        if self._pv is None:
            return
        p = self._pv
        presets = {
            "haut": lambda: p.view_xy(),
            "bas": lambda: p.view_xy(negative=True),
            "face": lambda: p.view_xz(),
            "arriere": lambda: p.view_xz(negative=True),
            "gauche": lambda: p.view_yz(),
            "droite": lambda: p.view_yz(negative=True),
            "iso": lambda: p.view_isometric(),
        }
        fn = presets.get(name)
        if fn is None:
            return
        try:
            fn()
            p.render()
        except Exception:
            pass

    # ------------------------------------------------ carte SPL (beamforming)
    def render(self, spl_values, points, grid_pts, geo_positions, config,
               show_spheres=False, restore_view=None):
        bf = {"SPL_map": spl_values, "points": points,
              "grid_pts": grid_pts, "geo_positions": geo_positions}
        buf = io.StringIO()
        import pyvista as pv
        from pyvistaqt import QtInteractor
        from src import beamforming
        inter = QtInteractor(self)
        orig = pv.Plotter
        pv.Plotter = lambda *a, **k: inter
        try:
            with contextlib.redirect_stdout(buf):
                beamforming.plot_beamforming(
                    cfg=config, SPL_values=bf["SPL_map"], points=bf["points"],
                    coordinates_list=bf["grid_pts"], geo_positions=bf["geo_positions"],
                    show_spheres=show_spheres)
        finally:
            pv.Plotter = orig
        self._set_widget(inter)
        self._pv = inter
        self._apply_view(restore_view)
        return buf.getvalue()

    # ------------------------------------------------ apercu scene (STL + antenne)
    def render_scene(self, points, grid_pts, geo_positions, config, restore_view=None):
        import numpy as np
        import pyvista as pv
        from pyvistaqt import QtInteractor

        pts = np.asarray(points, dtype=float)              # (n_tri, 3, 3)
        grid = pts.reshape(-1, 3)
        n_tri = pts.shape[0]
        faces = np.hstack([np.full((n_tri, 1), 3),
                           np.arange(n_tri * 3).reshape(-1, 3)]).astype(np.int64)
        mesh = pv.PolyData(grid, faces)

        inter = QtInteractor(self)
        try:
            inter.set_background(_BG)
        except Exception:
            pass
        inter.add_mesh(mesh, color=_MESH, show_edges=False)
        geo = np.asarray(geo_positions, dtype=float)
        if geo.size:
            inter.add_mesh(pv.PolyData(geo), color=_MIC, point_size=7,
                           render_points_as_spheres=True)
        inter.add_axes()
        try:
            inter.show_bounds(location="outer", ticks="outside", grid=False,
                              xtitle="X (m)", ytitle="Y (m)", ztitle="Z (m)", color="gray")
        except Exception:
            pass
        inter.reset_camera()
        self._set_widget(inter)
        self._pv = inter
        self._apply_view(restore_view)
        return ""
