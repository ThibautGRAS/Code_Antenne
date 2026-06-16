# -*- coding: utf-8 -*-
"""
Rendu overlay acoustique sur image caméra.
"""


import cv2
import numpy as np


class AcousticOverlayRenderer:
    def __init__(self, config, projection, theta, phi):
        self.config = config
        self.projection = projection
        self.theta = theta
        self.phi = phi

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
        overlay_lin = self.projection.interpolate_to_pixels(WB_lin)

        max_lin = float(np.max(overlay_lin) + self.config.eps_lin)

        overlay_dB = 10.0 * np.log10(
            (overlay_lin + self.config.eps_lin)
            / max_lin
        )

        vmin = -abs(dyn_dB)
        overlay_dB = np.clip(overlay_dB, vmin, 0.0)

        norm01 = (overlay_dB - vmin) / (0.0 - vmin + 1e-12)
        norm01 = np.clip(norm01, 0.0, 1.0)

        alpha_px = (norm01 ** alpha_gamma) * alpha_scale
        alpha_px = np.clip(alpha_px, 0.0, 1.0)

        alpha_px[~self.projection.mask] = 0.0

        heat_u8 = (255.0 * norm01).astype(np.uint8)

        cmap = cv2.COLORMAP_TURBO if use_turbo else cv2.COLORMAP_JET
        heat = cv2.applyColorMap(heat_u8, cmap)

        a3 = np.dstack(
            [alpha_px, alpha_px, alpha_px]
        ).astype(np.float32)

        blended = (
            image_bgr.astype(np.float32) * (1.0 - a3)
            + heat.astype(np.float32) * a3
        ).astype(np.uint8)

        if show_max:
            self.draw_max_cross(blended, WB_lin)

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