# -*- coding: utf-8 -*-
"""
Configuration live pour caméra acoustique MU32.

- Les paramètres qui changent souvent sont dans config_live.yaml.
- Les constantes, chemins internes et paramètres dérivés restent ici.
"""

from pathlib import Path
import numpy as np
import yaml


class Config:
    def __init__(self, yaml_file=None, **overrides):
        # ============================================================
        # 📁 Dossiers internes
        # ============================================================
        self.base_dir = Path(__file__).resolve().parent

        # Racine du projet : src/live/config_live.py -> parents[2]
        # à adapter si ton arborescence est différente
        self.project_dir = self.base_dir.parents[1]

        # Dossiers standards du projet live
        self.data_live_dir = self.base_dir / "data_live"
        self.data_calib_dir = self.base_dir / "data_calib"
        self.data_geo_dir = self.base_dir / "data_geo"
        self.data_output_dir = self.base_dir / "outputs"
        self.assets_dir = self.base_dir / "assets"

        # ============================================================
        # Constantes fixes
        # ============================================================
        # Sensibilité MEMS.
        # À figer ici si c'est une constante matérielle.
        self.SMEMS = 2**23 * 10**(-26 / 20) / np.sqrt(2)

        # Référence acoustique
        self.p_ref = 2e-5

        # Petite valeur numérique
        self.eps_lin = 1e-18
        self.eps_pressure = 1e-20

        # Vitesse du son par défaut
        self.c0 = 343.0

        # ============================================================
        # 📄 YAML
        # ============================================================
        if yaml_file is None:
            self.yaml_file = self.base_dir / "config_live.yaml"
        else:
            self.yaml_file = Path(yaml_file)

        self._load_yaml()

        # Overrides éventuels venant du main
        if overrides:
            self.update(overrides)

        self._compute_derived()

    # ============================================================
    # Chargement YAML
    # ============================================================
    def _load_yaml(self):
        if not self.yaml_file.exists():
            raise FileNotFoundError(f"Fichier YAML introuvable : {self.yaml_file}")

        with open(self.yaml_file, "r", encoding="utf-8") as f:
            params = yaml.safe_load(f) or {}

        for key, value in params.items():
            setattr(self, key, value)

    # ============================================================
    # UPDATE
    # ============================================================
    def update(self, params: dict):
        """
        Recharge le YAML puis applique les paramètres fournis par le main.
        Les paramètres du main sont prioritaires.
        """
        self._load_yaml()

        for key, value in params.items():
            setattr(self, key, value)

        self._compute_derived()

    # ============================================================
    # Dérivés
    # ============================================================
    def _compute_derived(self):
        """
        Recalcule les chemins et constantes dépendantes du YAML.
        """

        # ----------------------------
        # Fichiers
        # ----------------------------
        self.geo_file = self.data_geo_dir / self.geo_name
        self.calib_file = self.data_live_dir / self.calib_name

        # Dossier de sortie live
        self.output_folder = self.data_output_dir / self.session_name
        self.output_folder.mkdir(parents=True, exist_ok=True)

        # ----------------------------
        # Acquisition / buffer
        # ----------------------------
        self.win_samp = int(round(self.Tw * self.Fe))
        self.hop_samp = int(round(self.Th * self.Fe))

        if self.win_samp <= 0:
            raise ValueError("Tw invalide : win_samp <= 0")

        if self.hop_samp <= 0:
            raise ValueError("Th invalide : hop_samp <= 0")

        if self.hop_samp > self.win_samp:
            raise ValueError("Th doit être <= Tw")

        # Fréquence max autorisée
        self.f_max = self.f_max_factor * self.Fe

        # ----------------------------
        # Grille angulaire
        # ----------------------------
        self.phi = np.linspace(
            self.phi_min,
            self.phi_max,
            self.Lphi,
            endpoint=False,
            dtype=float,
        )

        self.dphi = (self.phi_max - self.phi_min) / self.Lphi

        # theta sera souvent recalculé après lecture calibration caméra,
        # car theta_max dépend de la focale.
        self.theta = None
        self.theta_max = None

        # ----------------------------
        # Caméra
        # ----------------------------
        self.cam_offset = np.array(self.cam_offset, dtype=np.float64)

        # ----------------------------
        # Logos
        # ----------------------------        
        self.cetim_logo_path = self.assets_dir / self.cetim_logo_file

        # ----------------------------
        # Vérifications simples
        # ----------------------------
        if self.f_start < self.f_min:
            raise ValueError("f_start est inférieur à f_min")

        if self.f_start > self.f_max:
            raise ValueError("f_start est supérieur à f_max")

        if self.delta_f <= 0:
            raise ValueError("delta_f doit être > 0")