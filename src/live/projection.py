# -*- coding: utf-8 -*-
"""
Projection entre l'image caméra et la grille angulaire beamforming.

Rôle :
- pré-calculer le mapping pixel -> (theta, phi)
- calculer les indices d'interpolation bilinéaire dans la carte BF
- projeter une direction DOA (theta, phi) vers un pixel image
"""

import math
import numpy as np
import cv2


class CameraBFProjection:
    def __init__(self, config, newK, w, h, theta, phi, theta_max):
        self.config = config
        self.newK = newK

        self.w = int(w)
        self.h = int(h)

        self.theta = theta
        self.phi = phi
        self.theta_max = float(theta_max)

        self.D = float(config.proj_distance_m)

        self.mask = None
        self.mask_f = None

        self.idx00 = None
        self.idx01 = None
        self.idx10 = None
        self.idx11 = None

        self.wt_f = None
        self.wp_f = None

        self._precompute()

    def _precompute(self):
        """
        Pré-calcule les indices et poids d'interpolation bilinéaire
        entre pixels caméra et carte beamforming.
        """
        uu, vv = np.meshgrid(
            np.arange(self.w, dtype=np.float64),
            np.arange(self.h, dtype=np.float64),
        )

        x = (uu - self.newK[0, 2]) / self.newK[0, 0]
        y = (vv - self.newK[1, 2]) / self.newK[1, 1]

        norm = np.sqrt(x * x + y * y + 1.0)

        dx_cam = x / norm
        dy_cam = y / norm
        dz_cam = 1.0 / norm

        t = self.config.cam_offset.astype(np.float64).reshape(1, 1, 3)

        P_ant = t + self.D * np.dstack((dx_cam, dy_cam, dz_cam))

        dir_ant = P_ant / (
            np.linalg.norm(P_ant, axis=2, keepdims=True)
            + 1e-15
        )

        dx_a = dir_ant[:, :, 0]
        dy_a = dir_ant[:, :, 1]
        dz_a = dir_ant[:, :, 2]

        if self.config.flip_x:
            dx_a = -dx_a

        theta_px = np.degrees(
            np.arccos(
                np.clip(dz_a, -1.0, 1.0)
            )
        )

        phi_px = np.degrees(
            np.arctan2(dy_a, dx_a)
        )

        phi_px = (phi_px + 360.0) % 360.0

        self.mask = theta_px <= self.theta_max
        self.mask_f = self.mask.ravel()

        # ----------------------------
        # Interpolation theta
        # ----------------------------
        t1 = np.searchsorted(
            self.theta,
            theta_px,
            side="right",
        ).astype(np.int32)

        t0 = (t1 - 1).astype(np.int32)

        t0 = np.clip(t0, 0, self.config.Ltheta - 2)
        t1 = t0 + 1

        theta0 = self.theta[t0]
        theta1 = self.theta[t1]

        wt = (theta_px - theta0) / (theta1 - theta0 + 1e-12)
        wt = np.clip(wt, 0.0, 1.0).astype(np.float32)

        # ----------------------------
        # Interpolation phi
        # ----------------------------
        dphi = float(self.config.dphi)

        p0 = np.floor(phi_px / dphi).astype(np.int32)
        p0 = np.mod(p0, self.config.Lphi)

        p1 = (p0 + 1) % self.config.Lphi

        phi0 = p0.astype(np.float64) * dphi

        wp = ((phi_px - phi0) / dphi).astype(np.float32)
        wp = np.clip(wp, 0.0, 1.0)

        # ----------------------------
        # Cartes de coordonnees pour cv2.remap (theta = ligne, phi = colonne).
        # phi est circulaire -> on echantillonne dans [0, Lphi], la colonne Lphi
        # (copie de la colonne 0) etant ajoutee au moment du remap. Memes poids
        # bilineaires que l'ancien gather (wt entre t0/t0+1, wp entre p0/p0+1).
        # ----------------------------
        self.map_y = (t0.astype(np.float32) + wt).astype(np.float32)
        self.map_x = (p0.astype(np.float32) + wp).astype(np.float32)

    def interpolate_to_pixels(self, WB_lin):
        """
        Interpole une carte beamforming angulaire vers les pixels caméra.

        Parameters
        ----------
        WB_lin : ndarray, shape (Ltheta, Lphi)
            Carte beamforming linéaire.

        Returns
        -------
        overlay_lin : ndarray, shape (h, w)
            Carte interpolée sur l'image caméra.
        """
        wb = np.ascontiguousarray(WB_lin, dtype=np.float32)

        # Padding circulaire d'une colonne en phi pour gerer le wrap.
        wb_pad = np.empty((wb.shape[0], wb.shape[1] + 1), dtype=np.float32)
        wb_pad[:, :-1] = wb
        wb_pad[:, -1] = wb[:, 0]

        # Echantillonnage bilineaire optimise (C/SIMD).
        out = cv2.remap(
            wb_pad, self.map_x, self.map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )

        out[~self.mask] = 0.0
        return out

    def doa_to_pixel(self, theta_deg, phi_deg):
        """
        Projette une direction DOA (theta, phi) vers un pixel caméra.

        Parameters
        ----------
        theta_deg : float
            Angle polaire en degrés.
        phi_deg : float
            Angle azimutal en degrés.

        Returns
        -------
        tuple[int, int] or None
            Pixel (u, v) si visible, sinon None.
        """
        th0 = math.radians(theta_deg)
        ph0 = math.radians(phi_deg)

        dx0 = math.cos(ph0) * math.sin(th0)
        dy0 = math.sin(ph0) * math.sin(th0)
        dz0 = math.cos(th0)

        if self.config.flip_x:
            dx0 = -dx0

        Px0 = self.D * dx0 - float(self.config.cam_offset[0])
        Py0 = self.D * dy0 - float(self.config.cam_offset[1])
        Pz0 = self.D * dz0 - float(self.config.cam_offset[2])

        if Pz0 <= 1e-9:
            return None

        u0 = int(round(self.newK[0, 0] * (Px0 / Pz0) + self.newK[0, 2]))
        v0 = int(round(self.newK[1, 1] * (Py0 / Pz0) + self.newK[1, 2]))

        if 0 <= u0 < self.w and 0 <= v0 < self.h:
            return (u0, v0)

        return None