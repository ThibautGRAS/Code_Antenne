# -*- coding: utf-8 -*-
"""
Created on Wed Nov 26 10:50:07 2025

@author: gras
"""

import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.widgets import Button
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from stl import mesh


# ============================================================================
# VISUALISATION - Generale
# ============================================================================

def print_section(title):
    print("\n" + "#" * 55)
    print(f"# {title}")
    print("#" * 55 + "\n")
    
    
def get_camera(ax):
    """Retourne l'orientation et la distance effective de la caméra."""
    elev = ax.elev
    azim = ax.azim

    # centre de la scène
    x0, x1 = ax.get_xlim3d()
    y0, y1 = ax.get_ylim3d()
    z0, z1 = ax.get_zlim3d()
    center = np.array([(x0+x1)/2, (y0+y1)/2, (z0+z1)/2])

    # distance effective = rayon de la scène
    R = max(x1-x0, y1-y0, z1-z0)

    return elev, azim, center, R

def set_camera(ax, elev, azim, center, R):
    """Applique orientation et distance effective à un autre axe."""
    ax.view_init(elev=elev, azim=azim)

    # appliquer les mêmes limites pour reproduire la distance caméra
    ax.set_xlim(center[0] - R/2, center[0] + R/2)
    ax.set_ylim(center[1] - R/2, center[1] + R/2)
    ax.set_zlim(center[2] - R/2, center[2] + R/2)


# ============================================================================
# VISUALISATION
# ============================================================================

def add_sphere_with_hps(ax, hp_indices=None, center=(0,0,0), R=0.1, 
                        rotation_deg=0, show_sphere=True, 
                        sphere_color='lightblue', sphere_alpha=0.2,
                        hp_color='red', hp_radius=0.01,
                        teta_deg=None, delta_deg=None,offset = 0.05):
    """
    Ajoute une sphère 3D optionnelle et les HP tracés comme des petites sphères.
    """
    cx, cy, cz = center
    rotation_rad = np.radians(rotation_deg)

    # Valeurs par défaut si None
    if teta_deg is None:
        teta_deg  = np.array([0, 270, 180, 90, 315, 225, 135, 45, 0, 270, 180, 90])
    if delta_deg is None:
        delta_deg = np.array([25, 45, 25, 45, 0,   0,   0,   0, -30, -45, -30, -45])
    
    # Sphère principale
    if show_sphere:
        plot_sphere(ax, center, R, color=sphere_color, alpha=sphere_alpha)

    # Positions HP
    teta = np.radians(teta_deg)
    delta = np.radians(delta_deg)
    x_hp = R * np.cos(delta) * np.cos(teta)
    y_hp = R * np.cos(delta) * np.sin(teta)
    z_hp = R * np.sin(delta)

    # rotation Z
    x_hp_rot = x_hp * np.cos(rotation_rad) - y_hp * np.sin(rotation_rad) + cx
    y_hp_rot = x_hp * np.sin(rotation_rad) + y_hp * np.cos(rotation_rad) + cy
    z_hp_rot = z_hp + cz
    
    # Décalage hors sphère
    
    x_hp_rot += offset * (x_hp_rot - cx)/R
    y_hp_rot += offset * (y_hp_rot - cy)/R
    z_hp_rot += offset * (z_hp_rot - cz)/R
    
    # Sélection des HP
    if hp_indices is not None:
        hp_indices_zero_based = [i-1 for i in hp_indices]
        x_hp_rot = x_hp_rot[hp_indices_zero_based]
        y_hp_rot = y_hp_rot[hp_indices_zero_based]
        z_hp_rot = z_hp_rot[hp_indices_zero_based]

    # Tracer les HP comme de petites sphères
    for x, y, z in zip(x_hp_rot, y_hp_rot, z_hp_rot):
        plot_sphere(ax, (x, y, z), radius=hp_radius, color=hp_color, alpha=1.0)
        
def get_cube_bounds(geo_positions):
    X, Y, Z = geo_positions[:,0], geo_positions[:,1], geo_positions[:,2]
    return (X.min(), X.max()), (Y.min(), Y.max()), (Z.min(), Z.max())

def offset_points_by_face(geo_positions, db_vals, bounds, offset, tol_face):
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds

    Xo, Yo, Zo, Co = [], [], [], []

    for ch, (x, y, z) in enumerate(geo_positions, start=1):
        db = db_vals.get(ch, np.nan)

        # offset selon face
        if abs(x - x_min) < tol_face:      x -= offset
        elif abs(x - x_max) < tol_face:    x += offset
        elif abs(y - y_min) < tol_face:    y -= offset
        elif abs(y - y_max) < tol_face:    y += offset
        elif abs(z - z_min) < tol_face:    z -= offset
        elif abs(z - z_max) < tol_face:    z += offset
        # sinon point interne → pas de modif

        Xo.append(x); Yo.append(y); Zo.append(z); Co.append(db)

    return Xo, Yo, Zo, Co


def plot_sphere(ax, center, radius, color, alpha=0.8, n_theta=12, n_phi=12):
    """Trace une petite sphère sur l'axe 3D ax."""
    u = np.linspace(0, 2*np.pi, n_theta)
    v = np.linspace(0, np.pi, n_phi)
    x = center[0] + radius*np.outer(np.cos(u), np.sin(v))
    y = center[1] + radius*np.outer(np.sin(u), np.sin(v))
    z = center[2] + radius*np.outer(np.ones_like(u), np.cos(v))
    ax.plot_surface(x, y, z, color=color, linewidth=0, antialiased=False, alpha=alpha, shade=True,zorder=10)
    
    
def add_stl_to_existing_ax(
    ax,
    stl_path,
    rotation_deg=(90, 0, 45+90+10+180),
    offsetx=1.0, offsety=0.9, offsetz=-0.33,
    facecolor='lightgray', edgecolor='none', alpha=0.6,
    scale=1.0,
    set_limits=True,
):
    """
    Ajoute un STL dans un Axes3D existant (ax) avec rotation autour du centre
    puis translation. Retourne (poly, triangles_world).

    - rotation_deg : (rx, ry, rz) en degrés, ordre appliqué : Rz @ Ry @ Rx
    - offsets et scale dans les mêmes unités que le STL
    """
    # Lecture STL -> (Ntri, 3, 3)
    stl_mesh = mesh.Mesh.from_file(stl_path)
    triangles = np.array(stl_mesh.vectors, dtype=float) * scale

    # Centre géométrique des points
    pts = triangles.reshape(-1, 3)
    center = pts.mean(axis=0)
    triangles_c = triangles - center

    # Matrices de rotation (ordre Z @ Y @ X)
    rx, ry, rz = np.deg2rad(rotation_deg)
    Rx = np.array([[1, 0, 0],
                   [0, np.cos(rx), -np.sin(rx)],
                   [0, np.sin(rx),  np.cos(rx)]])
    Ry = np.array([[ np.cos(ry), 0, np.sin(ry)],
                   [0,           1, 0          ],
                   [-np.sin(ry), 0, np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz), 0],
                   [np.sin(rz),  np.cos(rz), 0],
                   [0,           0,          1]])
    R = Rz @ Ry @ Rx

    # Application rotation + recentrage + translation
    triangles_world = (triangles_c @ R.T) + center + np.array([offsetx, offsety, offsetz])

    # Ajout au Axes3D existant
    poly = Poly3DCollection(triangles_world, facecolor=facecolor, edgecolor=edgecolor, alpha=alpha)
    ax.add_collection3d(poly)

    # Option: ajuster limites autour du STL ajouté
    if set_limits:
        all_pts = triangles_world.reshape(-1, 3)
        xmin, ymin, zmin = all_pts.min(axis=0)
        xmax, ymax, zmax = all_pts.max(axis=0)
        ax.set_xlim(min(ax.get_xlim()[0], xmin), max(ax.get_xlim()[1], xmax))
        ax.set_ylim(min(ax.get_ylim()[0], ymin), max(ax.get_ylim()[1], ymax))
        ax.set_zlim(min(ax.get_zlim()[0], zmin), max(ax.get_zlim()[1], zmax))
        ax.set_box_aspect([1, 1, 1])

    return poly


def prepare_plot_data(db_vals, geo_positions, config, dynamic_dB):
    """
    Prépare les bornes du cube et la normalisation couleur.
    - Si config.dyn est None ou 0 → dynamique complète (min → max)
    - Sinon → dynamique limitée (vmax - dyn → vmax)
    """
    bounds = get_cube_bounds(geo_positions)
    valid_vals = np.array([v for v in db_vals.values() if not np.isnan(v)])

    if valid_vals.size == 0:
        # Aucun niveau valide → normalisation par défaut
        return bounds, Normalize(0, 1)

    vmax = float(np.nanmax(valid_vals))
    vmin_data = float(np.nanmin(valid_vals))

    # Cas 1 : dynamique définie et > 0
    if getattr(config, "dyn", None) not in (None, 0):
        dyn = config.dyn
        vmin = vmax - dyn
        print(f"\n [OK] Dynamique couleur : [{vmin:.1f} dB ; {vmax:.1f} dB] (dyn={dyn} dB)")

    # Cas 2 : dynamique None ou 0 → min → max
    else:
        vmin = vmin_data
        print(f"\n [OK] Dynamique complete : [{vmin:.1f} dB ; {vmax:.1f} dB]")

    norm = Normalize(vmin=vmin, vmax=vmax)
    return bounds, norm

def plot_micro_spheres(ax, db_vals, chan_to_pos, bounds, config, norm):
    epsilon = config.offset_points_by_face

    for ch, pos in chan_to_pos.items():
        val = db_vals.get(ch, np.nan)
        if np.isnan(val):
            continue

        nudge = np.zeros(3)
        for i in range(3):
            if np.isclose(pos[i], bounds[i][0], atol=1e-4):
                nudge[i] = -epsilon
            elif np.isclose(pos[i], bounds[i][1], atol=1e-4):
                nudge[i] = epsilon

        new_pos = pos + nudge
        plot_sphere(ax, new_pos, config.sphere_radius, plt.cm.jet(norm(val)))

def plot_cube_edges(ax, bounds):
    (x_min, x_max), (y_min, y_max), (z_min, z_max) = bounds
    cube_vertices = np.array([
        [x_min, y_min, z_min], [x_max, y_min, z_min],
        [x_max, y_max, z_min], [x_min, y_max, z_min],
        [x_min, y_min, z_max], [x_max, y_min, z_max],
        [x_max, y_max, z_max], [x_min, y_max, z_max]
    ])
    edges = [
        (0,1), (1,2), (2,3), (3,0),
        (4,5), (5,6), (6,7), (7,4),
        (0,4), (1,5), (2,6), (3,7)
    ]
    for e in edges:
        p1, p2 = cube_vertices[e[0]], cube_vertices[e[1]]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], color='black', linewidth=1.5, alpha=0.6)

def add_view_buttons(fig, ax):
    def update_view(elev, azim):
        ax.view_init(elev=elev, azim=azim)
        fig.canvas.draw_idle()

    labels = ['Front', 'Top', 'Left', 'Right', 'Behind', 'Iso']
    views = [(0, -90), (90, -90), (0, 180), (0, 0), (0, 90), (30, -45)]

    for i, (label, (el, az)) in enumerate(zip(labels, views)):
        btn_ax = plt.axes([0.01, 0.9 - i*0.05, 0.08, 0.04])
        b = Button(btn_ax, label, color='lightgoldenrodyellow')
        b.on_clicked(lambda e, el=el, az=az: update_view(el, az))
        
        
