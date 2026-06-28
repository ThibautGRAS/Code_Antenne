# -*- coding: utf-8 -*-
"""
Created on Wed Apr  1 15:08:18 2026

@author: gras
"""
import matplotlib.pyplot as plt

from data.config import Config
from src import read_info,signal_process
from src import visu,power_acoustic

# ============================================================================
# SCRIPT PRINCIPAL
# ============================================================================
if __name__=="__main__":
    
    visu.print_section("Lancement du code de calcul de niveaux acoustiques du cube MEMS")
    visu.print_section("Chargement des données")
    
    plot_level = True 
    plot_power = True 
    plot_multi_mic = True 
    
    # ====================================================================
    # PARAMETRES DE CE RUN — editer ici. Override des defauts de config.yaml.
    # Une cle inconnue (absente de config.yaml) leve une erreur (anti-typo).
    # ====================================================================
    params_main = {
        "chosen_index": 0,     # index du fichier/mesure a analyser
        "chosen_band": 800,    # frequence d'affichage des niveaux (Hz)
        "dyn": None,           # dynamique dB des cartes (None = auto)
        "n_subdiv": 4,         # subdivision mesh pour la puissance
    }
    config = Config(overrides=params_main)
    
    ###################################################
    # Chargement des données
    ###################################################
    
    # chosen_index / chosen_band / dyn / n_subdiv : definis en tete (params_main)

    bands_corr, diff_corr = read_info.load_band_corrections(config)    
    Sigs_val, config = read_info.load_validation_data(config)    
    geo_positions = read_info.load_geo_positions(config)
    
    ###################################################
    # Calcul niveaux dB MEMS
    ###################################################
    visu.print_section("Calcul niveaux dB MEMS")
    
    all_results, chan_to_pos = signal_process.compute_all_mems_spectra(Sigs_val, geo_positions, config, window_type='hann') 
    
    db_vals = signal_process.extract_chosen_band_levels(all_results, config)
    
    chan_to_pos_sub = signal_process.select_mics_every_n(chan_to_pos, n=1) #Selection des micros à afficher
    
    ###################################################
    # Visualisation 3D - Niveaux dB 
    ###################################################
    if plot_level:
        visu.print_section("Visualisation 3D - Niveaux dB ")
        
        #Visualisation 3D - Niveaux dB - Mesh IDW
        fig,ax=visu.plot_mems_3d(db_vals,chan_to_pos_sub,geo_positions,config,mode='mesh',show_mics=False,alphaa=0.95, 
                                 dynamic_dB=config.dyn)    
        visu.add_sphere_with_hps(ax, center = (1.51/2,1.51/2,0.96), hp_indices=[1,2,3],R=0.1, rotation_deg=-45)           
        plt.show() 
        
        #Visualisation 3D - Niveaux dB - Mesh RBF
        fig,ax=visu.plot_mems_3d(db_vals,chan_to_pos_sub,geo_positions,config,mode='smooth',show_mics=False,
                            alphaa=0.9, dynamic_dB=config.dyn,method='thin_plate_spline', 
                            interp_space='Pa')     
        visu.add_sphere_with_hps(ax, center = (1.51/2,1.51/2,0.96), hp_indices=[1,2,3],R=0.1, rotation_deg=-45,offset = 0.0)
        plt.show()
        
    ###################################################
    # Puissance - Niveaux dB 
    ###################################################
    
    if plot_power: 
        visu.print_section("Puissance - Niveaux dB  ")
        # Tracé du cube 
        fig, ax, face_db, total_db = power_acoustic.plot_acoustic_power_on_cube(
            db_vals, chan_to_pos, geo_positions, config, config.n_subdiv 
        )
        plt.show() 
        
        # Exemple avec all_results et chan_to_pos déjà calculés
        fig, ax, W_faces_dB, W_total_dB, W_total_dB_global,freq = power_acoustic.acoustic_power_faces(all_results,
                                                                                       chan_to_pos, trace_total_only=False)
        
        # Puissance totale :
        fig2, ax2, _, W_total_dB,W_total_dB_global,freq = power_acoustic.acoustic_power_faces(all_results, 
                                                                               chan_to_pos, trace_total_only=True)
        
        power_acoustic.plot_power_comparison(freq, W_total_dB,config.ref_power_file,label_mems="240 MEMS",label_exp="9 MICROPHONES")
        

    ###################################################
    # Puissance - Niveaux dB multi micros
    ###################################################

    if plot_multi_mic:
        visu.print_section("Puissance - Niveaux dB multi micros   ")
        cube_Lx = 1.54
        cube_Ly = 1.54
        cube_Lz = 1.51
        St = 4*cube_Lx*cube_Lz + cube_Lx*cube_Ly
        
        mic_list = [76, 28, 212, 124, 172]
        
        # Tracé de la Puissance - Niveaux dB sur liste de micros  
        
        # "center5", "custom", "center5_topcorners"    
        freqs, W_dB, W_global_dB, selected, fig, ax, fig3d, ax3d, compare_results = power_acoustic.acoustic_power_selected_mems_hist(
            all_results,
            chan_to_pos,
            cube_Lx,
            cube_Ly,
            cube_Lz,
            surface_totale=St,
            origin=(0, 0, 0),
            mode="custom",
            custom_mics=mic_list,   
            compare_exp_file=config.ref_power_file,
            label_mems="MEMS center5",
            label_exp="MICROPHONES",
            fmin_compare=100,
            fmax_compare=20000
        )
        plt.show()
        
        # Tracé des niveaux dB sur liste de micros  
        visu.plot_third_octave_bars(all_results, mic_list)
        