# -*- coding: utf-8 -*-
"""
Etat dynamique du live.
"""

import time


class LiveState:
    def __init__(self, config):
        # ------------------------------------------------------------
        # Rendu acoustique
        # ------------------------------------------------------------
        self.dyn_dB = float(config.dyn_dB)
        self.alpha_scale = float(config.alpha_scale)
        self.alpha_gamma = float(config.alpha_gamma)

        self.use_turbo = False
        self.show_max = True

        # ------------------------------------------------------------
        # Frequence live
        # ------------------------------------------------------------
        self.f_center = float(config.f_start)

        # ------------------------------------------------------------
        # FPS
        # ------------------------------------------------------------
        self.t_last = time.perf_counter()
        self.fps = 0.0

        # ------------------------------------------------------------
        # Algorithmes live disponibles
        # ------------------------------------------------------------
        self.algorithms = [
            "BARTLETT_PLANE",
            "OBF_PLANE",
        ]

        self.algorithm_index = 0
        self.algorithm = self.algorithms[self.algorithm_index]

        # ------------------------------------------------------------
        # OBF : mode/source affiche
        # ------------------------------------------------------------
        self.obf_mode_index = 0
        self.obf_n_modes = 2

        # ------------------------------------------------------------
        # Modes d'affichage
        # ------------------------------------------------------------
        self.camera_only = False

        # ------------------------------------------------------------
        # Valeurs utiles pour l'UI
        # ------------------------------------------------------------
        self.last_f_real = None
        self.last_map_max_db = None
        self.last_map_min_db = None

    def update_fps(self):
        """
        Met a jour le FPS filtre.
        """
        now = time.perf_counter()
        dt = now - self.t_last
        self.t_last = now

        if dt > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)

        return self.fps

    def next_algorithm(self):
        """
        Passe a l'algorithme live suivant.
        """
        self.algorithm_index = (self.algorithm_index + 1) % len(self.algorithms)
        self.algorithm = self.algorithms[self.algorithm_index]
        print(f"[INFO] Algo live = {self.algorithm}")

    def previous_obf_mode(self):
        """
        Source/mode OBF precedent.
        """
        self.obf_mode_index = max(0, self.obf_mode_index - 1)
        print(f"[INFO] OBF source/mode = {self.obf_mode_index + 1}")

    def next_obf_mode(self):
        """
        Source/mode OBF suivant.
        """
        self.obf_mode_index = min(self.obf_n_modes - 1, self.obf_mode_index + 1)
        print(f"[INFO] OBF source/mode = {self.obf_mode_index + 1}")

    def toggle_camera_only(self):
        """
        Active/desactive l'affichage camera seule.
        """
        self.camera_only = not self.camera_only
        print(f"[INFO] camera_only={self.camera_only}")

    def algorithm_label(self):
        """
        Nom lisible de l'algorithme pour affichage.
        """
        if self.algorithm == "BARTLETT_PLANE":
            return "Bartlett plane"

        if self.algorithm == "OBF_PLANE":
            return f"OBF src {self.obf_mode_index + 1}/{self.obf_n_modes}"

        return self.algorithm