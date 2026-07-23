# -*- coding: utf-8 -*-
"""Affichage embarque.

- render()       : carte de beamforming (SPL) -> REUTILISE src.plot_beamforming
                   (rendu exact, avec colorbar). Sert aux etapes 3 / navigation OBF.
- render_scene() : apercu geometrie (STL + antenne) -> rendu PROPRE dedie, SANS
                   colorbar, objet en gris cadre en grand, micros en petits points rouges.
- capture_view()/restore : conserve la camera entre deux rendus (navigation OBF).
"""

import io
import contextlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

# Charte
_MESH = "#C1C7C6"     # gris froid (objet)
_EDGE = "#001E50"     # navy (aretes)
_MIC = "#EF3346"      # rouge (micros)
_BG = "#FFFFFF"


class ResultView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._current = None
        self._kind = None      # "mpl" | "pv"
        self._ax = None        # axes matplotlib courants
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

    # ------------------------------------------------ camera (navigation OBF)
    def capture_view(self):
        try:
            if self._kind == "pv" and self._pv is not None:
                return ("pv", self._pv.camera_position)
            if self._kind == "mpl" and self._ax is not None:
                return ("mpl", (self._ax.elev, self._ax.azim,
                                self._ax.get_xlim(), self._ax.get_ylim(), self._ax.get_zlim()))
        except Exception:
            pass
        return None

    def _apply_view(self, view):
        if not view:
            return
        kind, data = view
        try:
            if kind == "pv" and self._kind == "pv" and self._pv is not None:
                self._pv.camera_position = data
            elif kind == "mpl" and self._kind == "mpl" and self._ax is not None:
                elev, azim, xl, yl, zl = data
                self._ax.view_init(elev=elev, azim=azim)
                self._ax.set_xlim(xl)
                self._ax.set_ylim(yl)
                self._ax.set_zlim(zl)
                if self._ax.figure.canvas is not None:
                    self._ax.figure.canvas.draw_idle()
        except Exception:
            pass

    # ------------------------------------------------ carte SPL (beamforming)
    def render(self, spl_values, points, grid_pts, geo_positions, config,
               show_spheres=False, restore_view=None):
        bf = {"SPL_map": spl_values, "points": points,
              "grid_pts": grid_pts, "geo_positions": geo_positions}
        mode = str(getattr(config, "visual_mode", "pyvista")).lower()
        buf = io.StringIO()
        if mode == "matplotlib":
            self._render_matplotlib(bf, config, buf, show_spheres)
        else:
            self._render_pyvista(bf, config, buf, show_spheres)
        self._apply_view(restore_view)
        return buf.getvalue()

    def _call_plot(self, bf, config, show_spheres):
        from src import beamforming
        return beamforming.plot_beamforming(
            cfg=config, SPL_values=bf["SPL_map"], points=bf["points"],
            coordinates_list=bf["grid_pts"], geo_positions=bf["geo_positions"],
            show_spheres=show_spheres)

    def _render_matplotlib(self, bf, config, buf, show_spheres):
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        try:
            from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
        except Exception:
            NavigationToolbar2QT = None
        orig_show = plt.show
        plt.show = lambda *a, **k: None
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
        self._set_widget(container)
        self._kind, self._ax, self._pv = "mpl", wrapper.ax, None

    def _render_pyvista(self, bf, config, buf, show_spheres):
        import pyvista as pv
        from pyvistaqt import QtInteractor
        inter = QtInteractor(self)
        orig = pv.Plotter
        pv.Plotter = lambda *a, **k: inter
        try:
            with contextlib.redirect_stdout(buf):
                self._call_plot(bf, config, show_spheres)
        finally:
            pv.Plotter = orig
        self._set_widget(inter)
        self._kind, self._ax, self._pv = "pv", None, inter

    # ------------------------------------------------ apercu scene (STL + antenne)
    def render_scene(self, points, grid_pts, geo_positions, config, restore_view=None):
        mode = str(getattr(config, "visual_mode", "pyvista")).lower()
        if mode == "matplotlib":
            self._scene_matplotlib(points, geo_positions)
        else:
            self._scene_pyvista(points, geo_positions)
        self._apply_view(restore_view)
        return ""

    def _scene_matplotlib(self, points, geo_positions):
        import numpy as np
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        try:
            from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
        except Exception:
            NavigationToolbar2QT = None
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        pts = np.asarray(points, dtype=float)              # (n_tri, 3, 3)
        geo = np.asarray(geo_positions, dtype=float)

        fig = Figure()
        ax = fig.add_subplot(111, projection="3d")
        ax.add_collection3d(Poly3DCollection(
            [pts[i] for i in range(pts.shape[0])],
            facecolor=_MESH, edgecolor=_EDGE, linewidths=0.15, alpha=1.0))
        if geo.size:
            ax.scatter(geo[:, 0], geo[:, 1], geo[:, 2], c=_MIC, s=8, depthshade=False)

        allpts = pts.reshape(-1, 3)
        mn, mx = allpts.min(0), allpts.max(0)
        if geo.size:
            mn = np.minimum(mn, geo.min(0))
            mx = np.maximum(mx, geo.max(0))
        ax.set_xlim(mn[0], mx[0])
        ax.set_ylim(mn[1], mx[1])
        ax.set_zlim(mn[2], mx[2])
        try:
            ax.set_box_aspect(mx - mn)   # proportions reelles -> objet "en gros"
        except Exception:
            pass
        ax.set_xlabel("X [m]")
        ax.set_ylabel("Y [m]")
        ax.set_zlabel("Z [m]")

        container = QWidget()
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        canvas = FigureCanvasQTAgg(fig)
        if NavigationToolbar2QT is not None:
            lay.addWidget(NavigationToolbar2QT(canvas, container))
        lay.addWidget(canvas, 1)
        self._set_widget(container)
        self._kind, self._ax, self._pv = "mpl", ax, None

    def _scene_pyvista(self, points, geo_positions):
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
        inter.reset_camera()
        self._set_widget(inter)
        self._kind, self._ax, self._pv = "pv", None, inter
