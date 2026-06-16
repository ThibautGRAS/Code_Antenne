# -*- coding: utf-8 -*-
"""
Pipeline stages for acoustic processing (Complex operations only)
Simple data loading is handled directly in niveau_cube_new.py
"""

from typing import Any, Dict
import matplotlib.pyplot as plt

from src.pipelines.base import PipelineStage
from src import signal_process, visu, power_acoustic
from data.config import Config


class ComputeSpectraStage(PipelineStage):
    """Compute MEMS spectra"""
    
    def __init__(self, window_type: str = 'hann'):
        super().__init__("ComputeSpectra")
        self.window_type = window_type
        
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute all MEMS spectra"""
        all_results, chan_to_pos = signal_process.compute_all_mems_spectra(
            data["Sigs_val"],
            data["geo_positions"],
            data["config"],
            window_type=self.window_type
        )
        
        data["all_results"] = all_results
        data["chan_to_pos"] = chan_to_pos
        
        return data


class ExtractBandStage(PipelineStage):
    """Extract chosen frequency band levels"""
    
    def __init__(self, chosen_band: int = 800, mics_step: int = 1):
        super().__init__("ExtractBand")
        self.chosen_band = chosen_band
        self.mics_step = mics_step
        
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract band levels"""
        config = data["config"]
        config.chosen_band = self.chosen_band
        config.dyn = 10  # Set dynamic range for visualization
        
        db_vals = signal_process.extract_chosen_band_levels(
            data["all_results"],
            config
        )
        
        chan_to_pos_sub = signal_process.select_mics_every_n(
            data["chan_to_pos"],
            n=self.mics_step
        )
        
        data["db_vals"] = db_vals
        data["chan_to_pos_sub"] = chan_to_pos_sub
        
        return data


class VisualizationIDWStage(PipelineStage):
    """Visualize 3D beam pattern with IDW mesh"""
    
    def __init__(self, show_plot: bool = True):
        super().__init__("VisualizationIDW")
        self.show_plot = show_plot
        
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create IDW 3D visualization"""
        config = data["config"]
        
        fig, ax = visu.plot_mems_3d(
            data["db_vals"],
            data["chan_to_pos_sub"],
            data["geo_positions"],
            config,
            mode='mesh',
            show_mics=False,
            alphaa=0.95,
            dynamic_dB=config.dyn
        )
        
        if self.show_plot:
            plt.show()
        
        data["fig_idw"] = fig
        data["ax_idw"] = ax
        
        return data


class VisualizationRBFStage(PipelineStage):
    """Visualize 3D beam pattern with RBF smooth"""
    
    def __init__(self, show_plot: bool = True):
        super().__init__("VisualizationRBF")
        self.show_plot = show_plot
        
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create RBF 3D visualization"""
        config = data["config"]
        
        fig, ax = visu.plot_mems_3d(
            data["db_vals"],
            data["chan_to_pos_sub"],
            data["geo_positions"],
            config,
            mode='smooth',
            show_mics=False,
            alphaa=0.9,
            dynamic_dB=config.dyn,
            method='thin_plate_spline',
            interp_space='Pa'
        )
        
        
        if self.show_plot:
            plt.show()
        
        data["fig_rbf"] = fig
        data["ax_rbf"] = ax
        
        return data


class PowerAcousticVisualizationStage(PipelineStage):
    """Visualize acoustic power distribution on cube subdivisions"""
    
    def __init__(self, n_subdiv: int = 4, show_plot: bool = True):
        super().__init__("PowerAcousticVisualization")
        self.n_subdiv = n_subdiv
        self.show_plot = show_plot
        
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create acoustic power visualization on cube"""
        config = data["config"]
        config.n_subdiv = self.n_subdiv
        
        fig, ax, face_db, total_db = power_acoustic.plot_acoustic_power_on_cube(
            data["db_vals"],
            data["chan_to_pos"],
            data["geo_positions"],
            config,
            self.n_subdiv
        )
        
        if self.show_plot:
            plt.show()
        
        data["fig_power"] = fig
        data["ax_power"] = ax
        data["face_db"] = face_db
        data["total_db"] = total_db
        
        return data
