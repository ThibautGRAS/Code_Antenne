# -*- coding: utf-8 -*-
"""
Created on Wed Apr  1 15:08:18 2026

@author: gras
"""
import matplotlib.pyplot as plt
import numpy as np

from data.config import Config
from src import read_info,signal_process
from src import visu,power_acoustic,beamforming

from src.beamforming.beamforming_visu import MatplotlibWrapper, PyVistaWrapper


# ============================================================================
# SCRIPT PRINCIPAL
# ============================================================================
if __name__=="__main__":
    
    visu.print_section("Lancement du code de calcul de beamforming du cube MEMS")
    visu.print_section("Chargement des données")
    
    config=Config()
    
    ###################################################
    # Chargement des données
    ###################################################
    
    # ============================
    # Paramètres spectre / bande BEAMFORMING
    # ============================
    params_main = {  
    
        "df_band_bf": 1,              # → largeur bande (tiers / Δf)
        "chosen_band_bf": 1200.0,     # → bande centrale affichée (Hz)
        "fmin_bf": 1600,              # → fréquence min BF (Hz)
        "fmax_bf": 1650,              # → fréquence max BF (Hz)
        "delta_f": 100,               # → résolution MIScalc (Hz)
    
        "method": "bartlett",            # → bartlett / music / obf
        "n_sources": 3,               # → nb sources MUSIC
        "diag_remove": True,          # → remove diag CSM
        "z": 0,                       # → plan réfléchi z=z0 (None=off)
        "nmodei": None,               # → nb modes OBF (None=all)
    
        # ============================
        # Paramètres MESH
        # ============================
        "factor": 0.98,               # → échelle mesh
        "offsetx": 0.745,             # → offset X (m)
        "offsety": 0.745,              # → offset Y (m)
        "offsetz": 0,              # → offset Z (m)
        
        "mesh_name": "Aspi6.stl",   # → fichier STL utilisé        
        "obj_name": "Aspi6.obj",       # → Nom objet .obj
        # ============================
        # Paramètres géométriques / micros
        # ============================
        "max_angle_deg": None,        # → angle max pour micros
    
        # ============================
        # Visualisation
        # ============================
        "visual_mode": "pyvista",     # → pyvista / matplotlib
    
        # ============================
        # Paramètres fichiers / sélection
        # ============================
        "validation_name": "DATA_ASPI",   # → dossier contenant les signaux bruts
        "chosen_index": 1,                  # → index du fichier à analyser
    } 
    
    # Mise à jour dynamique
    config.update(params_main)
    
    print("Méthode BF :", config.method)
    print("Mesh utilisé :", config.file_mesh)
    
    config.chosen_index = 0
    config.validation_folder = config.data_valid / "DATA_ASPI"
        
    bands_corr, diff_corr = read_info.load_band_corrections(config)    
    raw_data, config = read_info.load_validation_data(config)    
    geo_positions = read_info.load_geo_positions(config)
    
    ###################################################
    # Beamforming 3D
    ###################################################
    visu.print_section("Beamforming 3D")
    
    # Étape 1 : calcul CSM
    Sigs_val = signal_process.extract_mic_signals(raw_data, config) # Extraction signaux micros et coefficient
    f_selected,selected_CSM = signal_process.MIScalc(Sigs_val, config)
    # Si volonte de selectionner :
    # f_selected,selected_CSM = signal_process.select_CSM(f_selected, selected_CSM, config.fmin_bf, config.fmax_bf, verbose=True)
          
    # Étape 2 : beamforming
    SPL_map, points, grid_pts = beamforming.run_beamforming_pipeline(
        f_selected,
        selected_CSM,
        geo_positions,
        config) 
    
    idx_max = np.argmax(SPL_map)
    source_pos = grid_pts[idx_max]   # (x, y, z)
    print(f"Source estimée {np.max(SPL_map):.2f} dB @ la position {source_pos}")
   
    
    # Nouvelle visualisation unifiée (PyVista ou Matplotlib automatiquement)
    plotter = beamforming.plot_beamforming(
        cfg=config,
        SPL_values=SPL_map,
        points=points,
        coordinates_list=grid_pts,show_spheres=False,
        geo_positions=geo_positions
    )
    title_str = f"BEAMFORMING - fmin = {config.fmin_bf:.1f} Hz, fmax = {config.fmax_bf:.1f} Hz, delta f = {config.df_band_bf:.1f} Hz"
    plotter.show(title=title_str)  # <-- titre défini ici
        
    # Si c’est Matplotlib
    if isinstance(plotter, MatplotlibWrapper):
        ax = plotter.get_ax()
        elev = 90
        azim = -90
        center = np.array([0.76225279, 0.76092942, 0.61344711])
        R = 0.223
        visu.set_camera(ax, elev, azim, center, R)
    
    plotter.show(title=title_str)
    