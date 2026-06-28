# -*- coding: utf-8 -*-
"""
Created on Wed Nov 26 10:50:07 2025

@author: gras
"""

import numpy as np

import os

# Backend interactif par defaut (sans ecraser un choix amont, ex. live -> Agg).
os.environ.setdefault("MPLBACKEND", "Qt5Agg")

from stl import mesh
import pyvista as pv

from src.visu import (
    get_cube_bounds,
    plot_cube_edges,
    add_view_buttons,
    plot_sphere
)  
  
   
def load_mesh(mesh_file, factor_dim):
    ext = os.path.splitext(mesh_file)[1].lower()

    if ext == '.stl':
        stl_mesh = mesh.Mesh.from_file(mesh_file)
        points = np.array(stl_mesh.vectors) / factor_dim

    elif ext == '.obj':
        mesh_pv = pv.read(mesh_file)
        faces = mesh_pv.faces.reshape(-1,4)[:,1:4]
        points = mesh_pv.points[faces] / factor_dim

    else:
        raise ValueError("Format mesh non supporté (STL/OBJ).")

    return points

def load_obj_pyvista(scanned_mesh):
    """
    Charge un OBJ PyVista + applique rotation, scale, offset, alignement Z.
    Retourne (mesh_obj, texture)
    """

    mesh_dir   = str(scanned_mesh["dir"])
    obj_name   = scanned_mesh["obj"]
    offset     = np.array(scanned_mesh["offset"])
    rotation   = scanned_mesh["rotation"]
    scale      = scanned_mesh["scale"]
    grayscale  = scanned_mesh["use_grayscale"]

    obj_file = os.path.join(mesh_dir, obj_name)
    mesh_obj = pv.read(obj_file)

    # --- Rotation autour du centre ---
    center = np.array(mesh_obj.center)
    mesh_obj.translate(-center, inplace=True)

    mesh_obj.rotate_x(rotation[0], inplace=True)
    mesh_obj.rotate_y(rotation[1], inplace=True)
    mesh_obj.rotate_z(rotation[2], inplace=True)

    mesh_obj.scale([scale, scale, scale], inplace=True)

    # --- Translation finale ---
    mesh_obj.translate(center + offset, inplace=True)

    # --- Texture diffuse ---
    texture = None
    tex_files = [f for f in os.listdir(mesh_dir) if "diffuse" in f.lower()]
    if tex_files:
        texture = pv.read_texture(os.path.join(mesh_dir, tex_files[0]))

    # --- Grayscale option ---
    if grayscale and texture is not None:
        arr = texture.to_array()
        if arr.shape[2] == 4:
            arr = arr[:, :, :3]
        gray = (0.299*arr[:,:,0] + 0.587*arr[:,:,1] + 0.114*arr[:,:,2]).astype(np.uint8)
        gray_rgb = np.stack([gray, gray, gray], axis=-1)
        texture = pv.numpy_to_texture(gray_rgb)

    return mesh_obj, texture

def transform_mesh(points, rotation_deg, offsetx, offsety, offsetz):
    grid_points_flat = points.reshape(-1,3)
    center = grid_points_flat.mean(axis=0)

    # rotation
    rx, ry, rz = np.deg2rad(rotation_deg)
    Rx = np.array([[1,0,0],[0,np.cos(rx),-np.sin(rx)],[0,np.sin(rx),np.cos(rx)]])
    Ry = np.array([[np.cos(ry),0,np.sin(ry)],[0,1,0],[-np.sin(ry),0,np.cos(ry)]])
    Rz = np.array([[np.cos(rz),-np.sin(rz),0],[np.sin(rz),np.cos(rz),0],[0,0,1]])
    Rmat = Rz @ Ry @ Rx

    points_centered = points - center
    points_rot = (points_centered @ Rmat.T) + center + np.array([offsetx,offsety,offsetz])

    return points_rot, points_rot.reshape(-1,3)



def scale_mesh_centered(mesh, factor):
    """
    Scale un mesh PyVista autour de son centre géométrique.
    
    Paramètres
    ----------
    mesh : pv.PolyData
        Le mesh à redimensionner (modifié in-place).
    factor : float ou tuple/list de 3 floats
        Facteur d'échelle. Exemple : 1.2 ou [1.2, 1.2, 1.2].
    """

    # 1) Centre du mesh
    center = np.array(mesh.center)

    # 2) Translation pour centrer
    mesh.translate(-center, inplace=True)

    # 3) Scaling
    mesh.scale([factor,factor,factor], inplace=True)

    # 4) Retour à la position d'origine
    mesh.translate(center, inplace=True)
    
    print('esh sclaed')

    return mesh


