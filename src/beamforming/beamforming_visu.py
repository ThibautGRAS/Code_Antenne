# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 14:37:06 2026

@author: gras
"""

import os

import numpy as np

# Backend interactif par defaut (sans ecraser un choix amont, ex. live -> Agg).
os.environ.setdefault("MPLBACKEND", "Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import pyvista as pv

from scipy.spatial import distance

from src.visu import (
    get_cube_bounds,
    plot_cube_edges,
    add_view_buttons,
    plot_sphere
)

from .beamforming_mesh import load_mesh, transform_mesh, load_obj_pyvista,scale_mesh_centered


class PyVistaWrapper:
    def __init__(self, plotter):
        self.plotter = plotter

    def show(self, title=None):
        # Appels multiples tolérés : une fois affiché/fermé, c'est un no-op
        # (gère le cas où le main appelle show() deux fois).
        if self.plotter is None:
            return
        try:
            if title:
                self.plotter.show(title=title)
            else:
                self.plotter.show()
        finally:
            # Ferme et désenregistre le plotter PENDANT que VTK est encore chargé,
            # puis lâche la référence : il est collecté immédiatement (et non au
            # shutdown, ce qui déclenchait les "Exception ignored in __del__ ...
            # 'NoneType' object has no attribute 'check_attribute'").
            try:
                import pyvista as pv
                pv.close_all()
            except Exception:
                pass
            self.plotter = None


class MatplotlibWrapper:
    def __init__(self, fig, ax):
        self.fig = fig
        self.ax = ax

    def show(self, title=None):
        if title:
            self.fig.suptitle(title)
        self.fig.show()

    def get_ax(self):
        return self.ax


def plot_beamforming(cfg, SPL_values, points, coordinates_list, geo_positions,show_spheres=False):
    """
    Fonction unifiée de visualisation :
    
    - Si cfg.obj_file existe → PyVista OBLIGATOIRE (OBJ + textures)
    - Sinon → mode choisi via cfg.visual_mode ("pyvista" ou "matplotlib")

    Paramètres :
        cfg : instance de Config
        SPL_values : valeurs SPL ou pseudo-spectrum
        points : triangles (faces) du mesh beamforming
        coordinates_list : liste des sommets utilisés pour SPL_values
        geo_positions : positions des MEMS
    """

    # ============================================================
    # 1) Choix automatique du mode
    # ============================================================
    if cfg.obj_file is not None:
        mode = "pyvista"   # OBJ → PyVista obligatoire
    else:
        mode = cfg.visual_mode.lower()

    # ============================================================
    # 2) Construction du dictionnaire scanned_mesh (si OBJ)
    # ============================================================
    scanned_mesh = None
    if cfg.obj_file is not None:
        scanned_mesh = {
            "dir": cfg.data_mesh,
            "obj": cfg.obj_name,
            "offset": (cfg.offsetx, cfg.offsety, cfg.offsetz),
            "rotation": tuple(cfg.rotation_deg),
            "scale": cfg.factor,
            "use_grayscale": cfg.use_grayscale_texture
        }
    # ============================================================
    # 2.5) Reconstruction EXACTE du mesh triangulé (comme avant)
    # ============================================================
    
    # points = mesh_tri dans ton pipeline
    points = np.asarray(points)
    
    # Si points est de la forme (n_triangles, 3, 3)
    if points.ndim == 3 and points.shape[1] == 3 and points.shape[2] == 3:
        print("✔ Reconstruction du mesh triangulé (format STL-like).")
    
        # Aplatir les sommets
        grid_points = points.reshape(-1, 3)
    
        # Générer les faces : 3 indices consécutifs par triangle
        faces = np.arange(points.shape[0] * 3).reshape(-1, 3)
    
    # Si points est déjà (n_points, 3) → pas un mesh triangulé
    else:
        raise ValueError(
            "❌ Le mesh fourni n'est pas triangulé. "            
        )



    # ============================================================
    # 3) Dispatch vers PyVista ou Matplotlib
    # ============================================================
    if mode == "pyvista":
        plotter = plot_beamforming_3D_interactive_pyvista(
            SPL_values=SPL_values,
            grid_points=coordinates_list,
            faces=faces,
            geo_positions=geo_positions,
            scanned_mesh=scanned_mesh,
            method=cfg.method,
            dynamic_dB=cfg.dyn,
            show_spheres=show_spheres,
            sphere_radius=cfg.sphere_radius, factor=cfg.factor,
            cmap=getattr(cfg, "cmap", "turbo"),
            ssao=getattr(cfg, "ssao", True),
            pbr=getattr(cfg, "pbr", True),
            halo=getattr(cfg, "halo", True),
            bg=getattr(cfg, "bg", "#16273F"),
            bg_top=getattr(cfg, "bg_top", "#0B1626"),
            fg=getattr(cfg, "fg", "#B8C4D6"),
            map_opacity=getattr(cfg, "map_opacity", 1.0),
        )
        return PyVistaWrapper(plotter)


    elif cfg.visual_mode == "matplotlib":
        fig, ax = plot_beamforming_3D_interactive_matplotlib(
            SPL_values=SPL_values,
            points=faces,
            coordinates_list=coordinates_list,
            geo_positions=geo_positions,
            method=cfg.method,
            dynamic_dB=cfg.dyn,
            show_spheres=show_spheres,
            sphere_radius=cfg.sphere_radius
        )
        return MatplotlibWrapper(fig, ax)


    else:
        raise ValueError(f"Mode inconnu : {mode}")


def plot_beamforming_3D_interactive_matplotlib(
    SPL_values, points, coordinates_list, geo_positions,
    method='bartlett', dynamic_dB=5,
    show_spheres=True, sphere_radius=0.01,
    alpha_face=1.0
):
    """
    Version Matplotlib : uniquement le mesh beamforming (pas d’OBJ).
    - points : liste des triangles (indices)
    - coordinates_list : sommets (N,3)
    - geo_positions : positions des MEMS
    """

    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    method_l = method.lower()

    # ============================================================
    # 1) Normalisation SPL
    # ============================================================
    if method_l in ['bartlett', 'obf']:
        vmax = np.max(SPL_values)
        vmin = vmax - dynamic_dB
    else:
        vmax = 0
        vmin = np.min(SPL_values)

    norm = Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.jet

    # ============================================================
    # 2) Figure
    # ============================================================
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor((1, 1, 1, 1))

    # ============================================================
    # 3) Beamforming mesh (triangles par indices)
    # ============================================================

    # Valeur SPL par face = moyenne des 3 sommets
    face_values = np.array([
        np.mean([SPL_values[v] for v in face])
        for face in points
    ])

    # Triangles = coordonnées réelles
    triangles = [
        [coordinates_list[v] for v in face]
        for face in points
    ]

    surface = Poly3DCollection(
        triangles,
        facecolors=cmap(norm(face_values)),
        edgecolors='none',
        alpha=alpha_face
    )
    ax.add_collection3d(surface)

    # ============================================================
    # 4) Micros
    # ============================================================
    if show_spheres:
        ax.scatter(*geo_positions.T, color='red', s=(sphere_radius * 1000)**2)

    # ============================================================
    # 5) Axes + labels
    # ============================================================
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_zlabel('Z [m]')
    ax.view_init(30, -45)
    ax.set_proj_type('ortho')
    
    add_view_buttons(fig, ax)

    # ============================================================
    # 6) Colorbar
    # ============================================================
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array(SPL_values)
    cbar = fig.colorbar(mappable, ax=ax, shrink=0.7, pad=0.1)
    cbar.set_label('SPL [dB]' if method_l in ['bartlett', 'obf'] else 'Pseudo-dB')

    plt.show()
    return fig, ax




def plot_beamforming_3D_interactive_pyvista(
    SPL_values, grid_points, faces, geo_positions,
    scanned_mesh=None,
    method='bartlett', dynamic_dB=5,
    show_spheres=False, sphere_radius=0.01, factor=1,
    cmap="turbo", ssao=True, pbr=True, halo=True,
    bg="#16273F", bg_top="#0B1626", fg="#B8C4D6", map_opacity=1.0,
):
    """
    Version factorisée PyVista avec OBJ optionnel.
    """

    method_l = method.lower()    

    # --- Normalisation SPL ---
    if method_l in ['bartlett', 'obf']:
        SPL_max = np.max(SPL_values)
        SPL_min = SPL_max - dynamic_dB
    else:
        SPL_max = 0
        SPL_min = np.min(SPL_values)

    SPL_display = np.clip(SPL_values, SPL_min, SPL_max)

    # --- Plotter ---
    plotter = pv.Plotter()
    # Fond sombre (degrade navy) integre a l'UI ; textes/axes en clair.
    try:
        plotter.set_background(bg, top=bg_top)
    except Exception:
        plotter.set_background(bg)
    # Rendu plus lisse et moderne (anti-crenelage).
    try:
        plotter.enable_anti_aliasing("fxaa")
    except Exception:
        pass

    # ============================================================
    # OBJ scanné (optionnel) OU STL de base
    # ============================================================
    if scanned_mesh is not None:
        mesh_obj, texture = load_obj_pyvista(scanned_mesh)
        
        center = grid_points.mean(axis=0)
        grid_points_scaled = grid_points.copy()  
        
        # 1) Centrage autour du même centre que le BF
        mesh_obj.points -= center
        
        # 2) Scaling
        mesh_obj.points *= factor
        
        # 3) Retour à la position d'origine
        mesh_obj.points += center
        
        # 4) Alignement Z (si nécessaire)
        z_min_stl = grid_points_scaled[:, 2].min()
        z_min_obj = mesh_obj.points[:, 2].min()
        mesh_obj.translate([0, 0, z_min_stl - z_min_obj], inplace=True)
        
        plotter.add_mesh(
            mesh_obj,
            texture=texture,
            show_edges=False,
            opacity=1.0
        )
        print("Scanned Object")
    
    else:
        # ============================================================
        # 2) Création d'une copie SCALÉE des points
        # ============================================================
        # 1) Centre du mesh
        center = grid_points.mean(axis=0)
        
        grid_points_scaled = grid_points.copy()        
        # Translation vers l'origine
        grid_points_scaled -= center        
        # Scaling
        grid_points_scaled *= factor        
        # Retour à la position d'origine
        grid_points_scaled += center
        
        # --- Affichage du STL de base (mesh brut) ---
        faces_pv_base = np.hstack([np.full((faces.shape[0], 1), 3), faces]).astype(np.int64)
        mesh_base = pv.PolyData(grid_points_scaled, faces_pv_base)
        
        base_kwargs = dict(color="lightgray", opacity=1, show_edges=False, smooth_shading=True)
        if pbr:   # materiau satine sur l'OBJET (pas sur la carte coloree -> elle reste visible)
            base_kwargs.update(pbr=True, metallic=0.2, roughness=0.5)
        plotter.add_mesh(mesh_base, **base_kwargs)
       


    # ============================================================
    # Mesh beamforming
    # ============================================================
    faces_pv_bf = np.hstack([np.full((faces.shape[0], 1), 3), faces]).astype(np.int64)
    mesh_bf = pv.PolyData(grid_points, faces_pv_bf)  
    
    scalar_name = {
        'bartlett': "SPL [dB SPL]",
        'obf':      "SPL [dB SPL]",
        'music':    "Pseudo-spectrum MUSIC",
        'omp':      "OMP activity (a.u.)"
    }.get(method_l, "Amplitude")

    # FONDU (comme les versions precedentes) : opacite proportionnelle au niveau -> 0 sous la
    # dynamique (transparent), jusqu'a map_opacity au pic. map_opacity = slider Transparence.
    SPL_norm = np.clip((SPL_display - SPL_min) / (SPL_max - SPL_min + 1e-12), 0.0, 1.0)
    opacity_array = float(map_opacity) * SPL_norm
    if len(SPL_values) == len(faces):
        mesh_bf.cell_data[scalar_name] = SPL_display
    else:
        mesh_bf.point_data[scalar_name] = SPL_display

    plotter.add_mesh(
        mesh_bf, scalars=scalar_name, cmap=cmap, clim=[SPL_min, SPL_max],
        opacity=opacity_array, show_edges=False, smooth_shading=True,
        scalar_bar_args=dict(
            title=scalar_name, vertical=True,
            position_x=0.88, position_y=0.12, width=0.07, height=0.76,
            title_font_size=15, label_font_size=12, n_labels=5, fmt="%.1f", color=fg,
        ),
    )


    

    # ============================================================
    # Micros
    # ============================================================
    if show_spheres:
        plotter.add_points(geo_positions, color='red', point_size=sphere_radius*1000)

    # ============================================================
    # Axes + grille
    # ============================================================
    plotter.add_axes()
    plotter.show_grid(color=fg)

    # Occlusion ambiante : relief/profondeur (effet "wahou").
    if ssao:
        try:
            plotter.enable_ssao(radius=0.15)
        except Exception:
            pass

    # Point chaud (max SPL) : petite bille AUTO-ILLUMINEE (glow) + lumiere ponctuelle chaude
    # qui eclaire reellement la surface autour de la source.
    if halo:
        try:
            gp = np.asarray(grid_points)
            hidx = int(np.argmax(SPL_values))
            if 0 <= hidx < len(gp):
                center = gp[hidx]
                diag = float(np.linalg.norm(gp.max(axis=0) - gp.min(axis=0)))
                r = max(4e-4, 0.006 * diag)   # petit repere : ne masque pas la carte
                # bille auto-illuminee (ambient=1, diffuse=0) -> parait emettre de la lumiere
                plotter.add_mesh(pv.Sphere(radius=r, center=center),
                                 color="#FFF6C8", ambient=1.0, diffuse=0.0, specular=0.0,
                                 opacity=0.95, smooth_shading=True)
                # vraie lumiere chaude a la source -> halo lumineux sur la surface
                try:
                    light = pv.Light(position=tuple(float(c) for c in center),
                                     color="#FFE39A")
                    light.positional = True
                    light.intensity = 0.9
                    plotter.add_light(light)
                except Exception:
                    pass
        except Exception:
            pass

    return plotter


def plot_beamforming_3D_interactive(
        SPL_values, points, coordinates_list, geo_positions,
        method='bartlett', show_spheres=True, sphere_radius=0.01,
        dynamic_dB=5, alpha_face=1):
    
    """
    Visualise la carto de beamforming.
    """

    method = method.lower()

    # --- Échelle SPL ---
    if method in ['bartlett', 'obf']:
        vmax = np.max(SPL_values)
        vmin = vmax - dynamic_dB
    elif method in ['music', 'omp']:
        vmax = 0
        vmin = np.min(SPL_values)
    else:
        raise ValueError(f"Méthode inconnue '{method}'.")

    norm = Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.jet

    # --- Figure ---
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')
    ax.set_facecolor((1, 1, 1, 1))

    # --- Valeurs par face ---
    coord_dict = {tuple(v): val for v, val in zip(coordinates_list, SPL_values)}
    face_values = np.array([
        np.mean([coord_dict[tuple(v)] for v in face])
        for face in points
    ])

    # --- Maillage coloré ---
    surface = Poly3DCollection(
        points,
        facecolors=cmap(norm(face_values)),
        edgecolors='none',
        alpha=alpha_face
    )
    ax.add_collection3d(surface)

    # --- MEMS ---
    if show_spheres:
        ax.scatter(*geo_positions.T, color='red', s=(sphere_radius * 1000)**2)

    # --- Cube englobant (utilise ta fonction existante) ---
    bounds = get_cube_bounds(geo_positions)
    plot_cube_edges(ax, bounds)

    # --- Axes ---
    ax.set_xlabel('X [m]')
    ax.set_ylabel('Y [m]')
    ax.set_zlabel('Z [m]')
    ax.view_init(30, -45)
    ax.set_proj_type('ortho')

    # --- Colorbar ---
    mappable = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    mappable.set_array(SPL_values)
    cbar = fig.colorbar(mappable, ax=ax, shrink=0.7, pad=0.1)
    cbar.set_label('SPL [dB]' if method == 'bartlett' else 'Pseudo-dB')

    # --- Boutons de vue (fonction déjà dans ton fichier) ---
    add_view_buttons(fig, ax)

    plt.show()
    return fig, ax

def compute_visibility_cone(grid_points, grid_normals,
                            mic_positions, max_angle_deg=90):
    """
    Visibilité micro-point par test angulaire robuste.
    La normale est retournée localement si nécessaire.
    """

    max_cos = np.cos(np.deg2rad(max_angle_deg))

    Np = grid_points.shape[0]
    Nm = mic_positions.shape[0]
    visibility = np.zeros((Np, Nm), dtype=bool)

    for i in range(Np):
        P = grid_points[i]
        n = grid_normals[i].copy()

        vec = mic_positions - P
        norms = np.linalg.norm(vec, axis=1)
        vec = vec / norms[:, None]

        # # 🔧 Correction orientation normale
        # vmean = np.mean(vec, axis=0)
        # if np.dot(n, vmean) < 0:
        #     n = -n

        cosang = vec @ n
        visibility[i] = cosang > max_cos

    return visibility

def compute_mesh_visibility(points, geo_positions, max_angle_deg, plot_visibility=False):
    v0, v1, v2 = points[:,0,:], points[:,1,:], points[:,2,:]
    normals = np.cross(v1 - v0, v2 - v0)

    center_grid = np.mean(points.reshape(-1,3), axis=0)
    for i,n in enumerate(normals):
        tri_center = (v0[i]+v1[i]+v2[i])/3
        if np.dot(n, center_grid - tri_center) > 0:
            normals[i] = -n

    norms = np.linalg.norm(normals, axis=1)
    normals[norms>1e-12] /= norms[norms>1e-12][:,None]
    normals[norms<=1e-12] = np.array([0,0,1])

    grid_normals = np.repeat(normals, 3, axis=0)

    visibility_mask = compute_visibility_cone(
        points.reshape(-1,3), grid_normals, geo_positions, max_angle_deg
    )

    if plot_visibility:
        plot_visible_mics(points, points.reshape(-1,3), grid_normals, visibility_mask, geo_positions)

    return visibility_mask

def plot_visible_mics(
    points,
    grid_points,
    grid_normals,
    visibility_mask,
    mic_positions,
    point_index=0,
    point_radius=0.01,
    normal_offset=0.01
):
    """
    Visualise les microphones visibles depuis un point STL,
    en utilisant EXACTEMENT la géométrie transformée.
    """

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # --------------------------------------------------
    # Surface STL/OBJ (déjà transformée)
    # --------------------------------------------------
    stl_poly = Poly3DCollection(
        points,
        facecolor='lightgray',
        edgecolor='none',
        alpha=0.6
    )
    ax.add_collection3d(stl_poly)

    # --------------------------------------------------
    # Micros
    # --------------------------------------------------
    ax.scatter(
        mic_positions[:, 0],
        mic_positions[:, 1],
        mic_positions[:, 2],
        color='gray',
        alpha=0.3,
        label='Micros (tous)'
    )

    visible_idx = np.where(visibility_mask[point_index])[0]
    ax.scatter(
        mic_positions[visible_idx, 0],
        mic_positions[visible_idx, 1],
        mic_positions[visible_idx, 2],
        color='red',
        s=30,
        label='Micros visibles'
    )

    # --------------------------------------------------
    # Point STL + normale
    # --------------------------------------------------
    P = grid_points[point_index]
    n = grid_normals[point_index]

    if np.linalg.norm(n) < 1e-12:
        n = np.array([0.0, 0.0, 1.0])
    n /= np.linalg.norm(n)

    P_visu = P + normal_offset * n

    if point_radius is None:
        point_radius = 0.01 * np.linalg.norm(
            grid_points.max(axis=0) - grid_points.min(axis=0)
        )

    plot_sphere(
        ax,
        center=P_visu,
        radius=point_radius,
        color='blue',
        alpha=1.0
    )

    ax.quiver(
        P[0], P[1], P[2],
        n[0], n[1], n[2],
        length=5 * normal_offset,
        color='blue'
    )

    # --------------------------------------------------
    # Mise en forme
    # --------------------------------------------------
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.legend()
    ax.set_box_aspect([1, 1, 1])

    all_pts = np.vstack([grid_points, mic_positions])
    ax.set_xlim(all_pts[:, 0].min(), all_pts[:, 0].max())
    ax.set_ylim(all_pts[:, 1].min(), all_pts[:, 1].max())
    ax.set_zlim(all_pts[:, 2].min(), all_pts[:, 2].max())
    
    # --- Boutons de vue ---
    add_view_buttons(fig, ax)

    plt.tight_layout()
    plt.show()