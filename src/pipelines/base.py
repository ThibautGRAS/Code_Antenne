# -*- coding: utf-8 -*-
"""
Pipeline base class for modular data processing
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class PipelineStage(ABC):
    """Abstract base class for pipeline stages"""
    
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the stage
        
        Args:
            data: Dictionary containing input data
            
        Returns:
            Dictionary containing output data
        """
        pass
    
    def __call__(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make stage callable"""
        logger.info(f"Executing stage: {self.name}")
        result = self.execute(data)
        logger.info(f"Stage {self.name} completed successfully")
        return result


class Pipeline:
    """Linear pipeline for sequential execution of stages"""
    
    def __init__(self, stages: List[PipelineStage], name: str = "Pipeline"):
        self.stages = stages
        self.name = name
        self.results = {}
        
    def add_stage(self, stage: PipelineStage):
        """Add a stage to the pipeline"""
        self.stages.append(stage)
        
    def run(self, initial_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Run the pipeline sequentially
        
        Args:
            initial_data: Initial data dictionary
            
        Returns:
            Final results dictionary
        """
        if initial_data is None:
            initial_data = {}
            
        logger.info(f"Starting pipeline: {self.name}")
        logger.info(f"Pipeline has {len(self.stages)} stages")
        
        current_data = initial_data.copy()
        
        for i, stage in enumerate(self.stages):
            logger.info(f"[{i+1}/{len(self.stages)}] {stage.name}")
            current_data = stage(current_data)
            self.results[stage.name] = current_data.copy()
            
        logger.info(f"Pipeline {self.name} completed successfully")
        return current_data
    
    def get_stage_result(self, stage_name: str) -> Dict[str, Any]:
        """Get results from a specific stage"""
        return self.results.get(stage_name, None)
    
    def __repr__(self) -> str:
        stage_names = " → ".join([s.name for s in self.stages])
        return f"Pipeline({self.name}): {stage_names}"
