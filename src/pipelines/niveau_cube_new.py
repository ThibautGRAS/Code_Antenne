# -*- coding: utf-8 -*-
"""
Acoustic pipeline for MEMS cube noise level computation
Compact and modular pipeline architecture
"""

from src.pipelines.base import Pipeline
from src.pipelines.stages import (
    ComputeSpectraStage,
    ExtractBandStage,
    VisualizationIDWStage,
    VisualizationRBFStage,
    PowerAcousticVisualizationStage
)
from src import read_info
from data.config import Config


def create_raw_data_pipeline(chosen_index: int = 1, window_type: str = 'hann') -> Pipeline:
    """Load and compute raw spectral data (one-time computation)"""
    
    # Load data directly (no wrapper stages needed)
    config = Config()
    config.chosen_index = chosen_index
    
    bands_corr, diff_corr = read_info.load_band_corrections(config)
    Sigs_val, _ = read_info.load_validation_data(config)
    geo_positions = read_info.load_geo_positions(config)
    
    # Initial data dict
    initial_data = {
        "config": config,
        "bands_corr": bands_corr,
        "diff_corr": diff_corr,
        "Sigs_val": Sigs_val,
        "geo_positions": geo_positions
    }
    
    # Only complex computation stages
    stages = [
        ComputeSpectraStage(window_type=window_type)
    ]
    
    pipeline = Pipeline(stages, name="RawDataPipeline")
    # Run with initial data
    return pipeline, initial_data


def create_visualization_pipeline(mode: str = 'idw', chosen_band: int = 800, 
                                  mics_step: int = 1, show_plot: bool = True) -> Pipeline:
    """Generic visualization pipeline (IDW, RBF, or Power)"""
    
    if mode == 'idw':
        stages = [
            ExtractBandStage(chosen_band=chosen_band, mics_step=mics_step),
            VisualizationIDWStage(show_plot=show_plot)
        ]
        name = "VisualizationIDWPipeline"
    elif mode == 'rbf':
        stages = [
            ExtractBandStage(chosen_band=chosen_band, mics_step=mics_step),
            VisualizationRBFStage(show_plot=show_plot)
        ]
        name = "VisualizationRBFPipeline"
    elif mode == 'power':
        stages = [
            ExtractBandStage(chosen_band=chosen_band, mics_step=mics_step),
            PowerAcousticVisualizationStage(n_subdiv=4, show_plot=show_plot)
        ]
        name = "PowerAcousticPipeline"
    else:
        raise ValueError(f"Unknown visualization mode: {mode}")
    
    return Pipeline(stages, name=name)
