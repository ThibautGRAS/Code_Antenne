# -*- coding: utf-8 -*-
"""
Gestion caméra live :
- ouverture caméra OpenCV
- réglage résolution
- lecture image
- correction de distorsion
"""

import cv2


class LiveCamera:
    def __init__(self, config, K, dist):
        self.config = config
        self.K = K
        self.dist = dist

        self.w = int(config.cam_w)
        self.h = int(config.cam_h)

        self.cap = None
        self.newK = None
        self.roi = None
        self.map1 = None
        self.map2 = None

    def start(self):
        """
        Ouvre la caméra et prépare les cartes d'undistortion.
        """
        self.cap = cv2.VideoCapture(
            self.config.cam_index,
            cv2.CAP_DSHOW,
        )

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Impossible d'ouvrir la caméra index={self.config.cam_index}"
            )

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.h)

        ok, frame0 = self.cap.read()

        if not ok:
            self.close()
            raise RuntimeError("Impossible de lire une frame caméra.")

        frame0 = cv2.resize(frame0, (self.w, self.h))

        self.newK, self.roi = cv2.getOptimalNewCameraMatrix(
            self.K,
            self.dist,
            (self.w, self.h),
            0.0,
            (self.w, self.h),
        )

        self.map1, self.map2 = cv2.initUndistortRectifyMap(
            self.K,
            self.dist,
            None,
            self.newK,
            (self.w, self.h),
            cv2.CV_16SC2,
        )

    def read_raw(self):
        """
        Lit une frame brute redimensionnée.
        """
        if self.cap is None:
            raise RuntimeError("Caméra non démarrée. Appeler start() avant read_raw().")

        ok, frame = self.cap.read()

        if not ok:
            return None

        frame = cv2.resize(frame, (self.w, self.h))
        return frame

    def read_undistorted(self):
        """
        Lit une frame caméra et applique la correction de distorsion.
        """
        frame = self.read_raw()

        if frame is None:
            return None

        und = cv2.remap(
            frame,
            self.map1,
            self.map2,
            cv2.INTER_LINEAR,
        )

        return und

    def close(self):
        """
        Libère la caméra.
        """
        if self.cap is not None:
            self.cap.release()
            self.cap = None