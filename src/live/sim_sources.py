# -*- coding: utf-8 -*-
"""
Sources de SIMULATION pour le live (memes interfaces que le materiel reel).

Permet de lancer l'application sans carte MU32 ni camera :
- SimAudioSource : onde plane coherente + bruit (pic de beamforming visible) ;
- SimCameraSource : image synthetique (fond degrade + marqueur + mention SIM).
"""

import math
import numpy as np
import cv2


class SimAudioSource:
    """
    Source audio synthetique : onde plane coherente venant d'une direction
    fixe (pour produire un pic de beamforming visible) + bruit. Le ton suit
    state.f_center pour rester visible quelle que soit la frequence affichee.
    """

    def __init__(self, config, geo_positions, state,
                 doa_theta_deg=18.0, doa_phi_deg=40.0):
        self.config = config
        self.geo = np.asarray(geo_positions, dtype=np.float64)
        self.n_ch = int(self.geo.shape[0])
        self.state = state
        self.fs = float(config.Fe)
        self._n = 0
        self.rng = np.random.default_rng(12345)

        th = math.radians(doa_theta_deg)
        ph = math.radians(doa_phi_deg)
        self.u = np.array([
            math.sin(th) * math.cos(ph),
            math.sin(th) * math.sin(ph),
            math.cos(th),
        ], dtype=np.float64)

    def start(self):
        pass

    def read_block(self, duration):
        n = max(1, int(round(duration * self.fs)))
        idx = np.arange(self._n, self._n + n)
        self._n += n
        t = idx / self.fs

        f = float(getattr(self.state, "f_center", self.config.f_start))
        k = 2.0 * math.pi * f / float(self.config.c0)

        # Dephasage par micro pour une onde plane venant de self.u.
        phase = k * (self.geo @ self.u)            # (n_ch,)

        tone = 0.2 * np.cos(2.0 * math.pi * f * t[:, None] + phase[None, :])
        noise = 0.02 * self.rng.standard_normal((n, self.n_ch))

        sig_pa = tone + noise                      # Pa
        block_counts = sig_pa * self.config.SMEMS  # le moteur divise par SMEMS

        return block_counts.astype(np.float64)

    def close(self):
        pass


class SimCameraSource:
    """Camera synthetique : fond degrade + marqueur mouvant + mention SIM."""

    def __init__(self, config, K):
        self.config = config
        self.w = int(config.cam_w)
        self.h = int(config.cam_h)
        self.newK = K
        self._n = 0

        ramp = np.linspace(30, 95, self.h).astype(np.uint8)
        base = np.repeat(ramp[:, None], self.w, axis=1)
        self._bg = cv2.merge([
            base,
            (base * 0.55).astype(np.uint8),
            (base * 0.28).astype(np.uint8),
        ])

    def start(self):
        pass

    def read_undistorted(self):
        img = self._bg.copy()
        self._n += 1

        cx = int(self.w * 0.5 + self.w * 0.25 * math.cos(self._n * 0.05))
        cy = int(self.h * 0.5 + self.h * 0.20 * math.sin(self._n * 0.05))

        cv2.circle(img, (cx, cy), 18, (60, 200, 255), 2, cv2.LINE_AA)
        cv2.putText(
            img, "SIMULATION", (12, self.h - 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 220, 255), 2, cv2.LINE_AA,
        )
        return np.ascontiguousarray(img)

    def close(self):
        pass
