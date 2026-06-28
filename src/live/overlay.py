# -*- coding: utf-8 -*-
"""
Rendu overlay acoustique sur image caméra.
"""


import time

import cv2
import numpy as np


class AcousticOverlayRenderer:
    def __init__(self, config, projection, theta, phi):
        self.config = config
        self.projection = projection
        self.theta = theta
        self.phi = phi

        # Cache de la LUT alpha (recalculee seulement si gamma/scale changent).
        self._alpha_lut_key = None
        self._alpha_lut_cache = None
        # Sous-profilage de render() (affiche une fois).
        self._prof = None
        self._prof_n = 0

    def _alpha_lut(self, gamma, scale):
        """LUT 256 entrees : niveau (0..255) -> alpha = clip((v/255)^gamma*scale)."""
        key = (round(float(gamma), 4), round(float(scale), 4))
        if key != self._alpha_lut_key:
            v = np.linspace(0.0, 1.0, 256, dtype=np.float32)
            self._alpha_lut_cache = np.clip(
                (v ** float(gamma)) * float(scale), 0.0, 1.0).astype(np.float32)
            self._alpha_lut_key = key
        return self._alpha_lut_cache

    def _profile(self, parts):
        """Moyenne glissante des sous-etapes ; affiche une fois (diagnostic)."""
        if self._prof is None:
            self._prof = list(parts)
        else:
            self._prof = [0.8 * a + 0.2 * b for a, b in zip(self._prof, parts)]
        self._prof_n += 1
        if self._prof_n == 20:
            ms = [x * 1000.0 for x in self._prof]
            print(f"[INFO] overlay (ms) : interp {ms[0]:.1f} | norm {ms[1]:.1f} | "
                  f"alpha {ms[2]:.1f} | colormap {ms[3]:.1f} | blend {ms[4]:.1f}")

    def render(
        self,
        image_bgr,
        WB_lin,
        dyn_dB,
        alpha_scale,
        alpha_gamma,
        use_turbo=False,
        show_max=True,
    ):
        """
        Superpose la carte beamforming sur l'image caméra.
        """
        t0 = time.perf_counter()

        # 1) Passage en dB sur la carte BF COARSE (peu de points) PUIS
        #    interpolation vers les pixels (1 seul gather plein ecran).
        max_lin = float(np.max(WB_lin) + self.config.eps_lin)
        db_map = 10.0 * np.log10((WB_lin + self.config.eps_lin) / max_lin)
        overlay_dB = self.projection.interpolate_to_pixels(db_map)
        t1 = time.perf_counter()

        # 2) Normalisation 0..1 (in-place).
        vmin = -abs(dyn_dB)
        np.clip(overlay_dB, vmin, 0.0, out=overlay_dB)
        norm01 = (overlay_dB - vmin) * (1.0 / (-vmin + 1e-12))
        np.clip(norm01, 0.0, 1.0, out=norm01)
        heat_u8 = (255.0 * norm01).astype(np.uint8)
        t2 = time.perf_counter()

        # 3) Alpha via LUT (evite un pow plein ecran) + masque.
        alpha_px = self._alpha_lut(alpha_gamma, alpha_scale)[heat_u8]
        alpha_px[~self.projection.mask] = 0.0
        t3 = time.perf_counter()

        # 4) Colormap.
        cmap = cv2.COLORMAP_TURBO if use_turbo else cv2.COLORMAP_JET
        heat = cv2.applyColorMap(heat_u8, cmap)
        t4 = time.perf_counter()

        # 5) Blend per-pixel in-place : blended = image + alpha*(heat - image).
        alpha = alpha_px[:, :, None]
        img_f = image_bgr.astype(np.float32)
        heat_f = heat.astype(np.float32)
        np.subtract(heat_f, img_f, out=heat_f)
        np.multiply(heat_f, alpha, out=heat_f)
        np.add(img_f, heat_f, out=img_f)
        blended = img_f.astype(np.uint8)
        t5 = time.perf_counter()

        if show_max:
            self.draw_max_cross(blended, WB_lin)

        self._profile((t1 - t0, t2 - t1, t3 - t2, t4 - t3, t5 - t4))
        return blended

    def draw_max_cross(self, image_bgr, WB_lin):
        """
        Dessine la croix au maximum de la carte BF.
        """
        iy, ix = np.unravel_index(
            int(np.argmax(WB_lin)),
            WB_lin.shape,
        )

        uv = self.projection.doa_to_pixel(
            float(self.theta[iy]),
            float(self.phi[ix]),
        )

        if uv is None:
            return image_bgr

        u0, v0p = uv
        Lc = 8

        cv2.line(
            image_bgr,
            (u0 - Lc, v0p),
            (u0 + Lc, v0p),
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        cv2.line(
            image_bgr,
            (u0, v0p - Lc),
            (u0, v0p + Lc),
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )

        return image_bgr