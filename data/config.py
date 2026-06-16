import numpy as np
from pathlib import Path
import yaml

class Config:
    def __init__(self):
        # ============================================================
        # 📁 Dossiers internes du package
        # ============================================================
        self.base_dir = Path(__file__).parent

        # Dossiers standards du projet
        self.data_calib_dir = self.base_dir / "data_calib"
        self.data_geo_dir   = self.base_dir / "data_geo"
        self.data_valid     = self.base_dir / "data_raw"
        self.data_ref       = self.base_dir / "data_ref"
        self.data_mesh      = self.base_dir / "data_mesh"
        
        self.SMEMS =  2**23 * 10**(-26/20) / np.sqrt(2) # Sensibilite MEMS

        # ============================================================
        # 📄 Chargement du fichier YAML
        # ============================================================
        self.yaml_file = self.base_dir / "config.yaml"
        with open(self.yaml_file, "r") as f:
            params = yaml.safe_load(f)

        # Injection dynamique
        for key, value in params.items():
            setattr(self, key, value)

        # Calcul des dérivés
        self._compute_derived()

    # ============================================================
    # 🔄 Fonction UPDATE
    # ============================================================
    def update(self, params: dict):
        """
        Recharge le YAML puis applique les paramètres du main.
        Recalcule ensuite les chemins dépendants.
        """
    
        # 1) Recharger le YAML (valeurs par défaut)
        with open(self.yaml_file, "r") as f:
            yaml_params = yaml.safe_load(f)
    
        for key, value in yaml_params.items():
            setattr(self, key, value)
    
        # 2) Appliquer les paramètres du main (prioritaires)
        for key, value in params.items():
            setattr(self, key, value)
    
        # 3) Recalcul des chemins et constantes dérivées
        self._compute_derived()


    # ============================================================
    # 🔧 Fonction interne pour recalculer les dérivés
    # ============================================================
    def _compute_derived(self):
        """Recalcule les chemins et constantes dépendantes du YAML."""

        # Chemins dépendants
        self.validation_folder = self.data_valid / self.validation_name
        self.geo_file = self.data_geo_dir / self.geo_name
        self.ref_power_file = self.data_ref / self.power_ref
        self.file_mesh = self.data_mesh / self.mesh_name
        self.calib_file = self.data_calib_dir / self.calib_name

        # OBJ optionnel
        self.obj_file = (
            self.data_mesh / self.obj_name if getattr(self, "obj_name", None) else None
        )

        # Dossier de sortie
        self.out_folder = self.data_calib_dir / "bands_output"
