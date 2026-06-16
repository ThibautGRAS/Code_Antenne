# -*- coding: utf-8 -*-
"""
Main entry point using simplified pipeline architecture
No wrappers for simple loading functions
"""

from src.pipelines.niveau_cube_new import create_raw_data_pipeline, create_visualization_pipeline
from src import visu

if __name__ == "__main__":
    print("=" * 80)
    print("Lancement du pipeline acoustique du cube MEMS")
    print("=" * 80)
    
    # Step 1: Load raw data and compute spectra (no cache)
    print("\n>>> Step 1: Loading and computing raw data...\n")
    pipeline_raw, raw_data = create_raw_data_pipeline(chosen_index=0, window_type='hann')
    raw_data = pipeline_raw.run(raw_data)
    
    # raw_data['config'].smooth_resolution = 10
    
    # Step 2-4: Multiple visualizations using same raw data
    print("\n>>> Step 2: Visualizing with IDW...\n")
    _ = create_visualization_pipeline(mode='idw', chosen_band=800, show_plot=True,mics_step=1).run(raw_data)
        
    print("\n>>> Step 3: Visualizing with RBF...\n")
    _ = create_visualization_pipeline(mode='rbf', chosen_band=800, show_plot=True,mics_step=1).run(raw_data)
    
    print("\n>>> Step 4: Visualizing acoustic power on cube...\n")
    _ = create_visualization_pipeline(mode='power', chosen_band=800, show_plot=True,mics_step=1).run(raw_data)
    
    print("\n" + "=" * 80)
    print("All pipelines executed successfully!")
    print("=" * 80)
