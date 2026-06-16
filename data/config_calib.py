import numpy as np
from pathlib import Path
import yaml


class Config:
    def __init__(self):
        # ============================================================
        # 📁 Dossiers internes du package
        # ============================================================
        self.base_dir = Path(__file__).parent
        self.data_calib_dir = self.base_dir / "data_calib"

        # Sensibilité MEMS
        self.SMEMS = 2**23 * 10**(-26 / 20) / np.sqrt(2)
        
        # ============================================================
        # 📄 Chargement du YAML
        # ============================================================
        self.yaml_file = self.base_dir / "config_calib.yaml"
        with open(self.yaml_file, "r", encoding="utf-8") as f:
            params = yaml.safe_load(f)

        for key, value in params.items():
            setattr(self, key, value)

        self._compute_derived()

    def update(self, params: dict):
        """
        Recharge les valeurs YAML puis applique les paramètres fournis.
        """
        with open(self.yaml_file, "r", encoding="utf-8") as f:
            yaml_params = yaml.safe_load(f)

        for key, value in yaml_params.items():
            setattr(self, key, value)

        for key, value in params.items():
            setattr(self, key, value)

        self._compute_derived()

    def _compute_derived(self):
        """
        Recalcule les chemins dérivés utiles à la calibration.
        """

        # Dossier contenant les fichiers de calibration
        # soit directement data_calib_dir
        # soit un sous-dossier si validation_name est renseigné
        validation_name = getattr(self, "validation_name", None)

        if validation_name:
            self.validation_folder = self.data_calib_dir / validation_name
        else:
            self.validation_folder = self.data_calib_dir

        # Dossier de sortie
        self.out_folder = self.validation_folder / "bands_output"
        self.out_folder.mkdir(parents=True, exist_ok=True)

        # Valeur par défaut si absente du YAML
        if not hasattr(self, "chosen_index"):
            self.chosen_index = 0