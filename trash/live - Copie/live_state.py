# -*- coding: utf-8 -*-
"""
État dynamique du live.
"""

import time


class LiveState:
    def __init__(self, config):
        self.dyn_dB = float(config.dyn_dB)
        self.alpha_scale = float(config.alpha_scale)
        self.alpha_gamma = float(config.alpha_gamma)

        self.use_turbo = False
        self.show_max = True

        self.f_center = float(config.f_start)

        self.t_last = time.perf_counter()
        self.fps = 0.0

        # Algorithmes live disponibles
        self.algorithms = [
            "BARTLETT_PLANE",
            "OBF_PLANE",
        ]

        self.algorithm_index = 0
        self.algorithm = self.algorithms[self.algorithm_index]

        # Pour OBF : mode/source affiché
        # 0 = source/mode principal, 1 = source/mode secondaire, etc.
        self.obf_mode_index = 0
        self.obf_n_modes = 2

    def update_fps(self):
        now = time.perf_counter()
        dt = now - self.t_last
        self.t_last = now

        if dt > 0:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / dt)

        return self.fps

    def next_algorithm(self):
        self.algorithm_index = (self.algorithm_index + 1) % len(self.algorithms)
        self.algorithm = self.algorithms[self.algorithm_index]
        print(f"[INFO] Algo live = {self.algorithm}")

    def previous_obf_mode(self):
        self.obf_mode_index = max(0, self.obf_mode_index - 1)
        print(f"[INFO] OBF source/mode = {self.obf_mode_index + 1}")

    def next_obf_mode(self):
        self.obf_mode_index = min(self.obf_n_modes - 1, self.obf_mode_index + 1)
        print(f"[INFO] OBF source/mode = {self.obf_mode_index + 1}")