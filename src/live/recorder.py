# -*- coding: utf-8 -*-
"""
Enregistrement vidéo de la fenêtre live.

Le recorder enregistre directement l'image dashboard affichée par OpenCV.
Nom automatique :
    rec_YYYYMMDD_HHMMSS.mp4
"""

from pathlib import Path
from datetime import datetime

import cv2


class LiveRecorder:
    """
    Gestion simple d'un enregistrement vidéo OpenCV.

    Utilisation :
        recorder.toggle(frame, config)
        recorder.write(frame)
        recorder.close()
    """

    def __init__(self):
        self.is_recording = False
        self.writer = None
        self.filepath = None
        self.frame_size = None
        self.fps = None

    def start(self, frame_bgr, config, fps=20.0):
        """
        Démarre un nouvel enregistrement vidéo.

        Parameters
        ----------
        frame_bgr : ndarray
            Image BGR actuellement affichée.
        config : Config
            Contient config.data_output_dir.
        fps : float
            FPS de la vidéo écrite.
        """
        if self.is_recording:
            return

        output_dir = Path(config.data_output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = output_dir / f"rec_{timestamp}.mp4"

        h, w = frame_bgr.shape[:2]
        self.frame_size = (w, h)
        self.fps = float(fps)

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        self.writer = cv2.VideoWriter(
            str(self.filepath),
            fourcc,
            self.fps,
            self.frame_size,
        )

        if not self.writer.isOpened():
            self.writer = None
            self.filepath = None
            self.frame_size = None
            self.fps = None
            self.is_recording = False
            print("[ERROR] Impossible d'ouvrir le VideoWriter")
            return

        self.is_recording = True
        print(f"[INFO] Enregistrement demarre : {self.filepath}")

    def stop(self):
        """
        Arrête l'enregistrement en cours.
        """
        if self.writer is not None:
            self.writer.release()

        if self.filepath is not None:
            print(f"[INFO] Enregistrement termine : {self.filepath}")

        self.is_recording = False
        self.writer = None
        self.filepath = None
        self.frame_size = None
        self.fps = None

    def toggle(self, frame_bgr, config, fps=20.0):
        """
        Bascule start / stop.
        """
        if self.is_recording:
            self.stop()
        else:
            self.start(frame_bgr=frame_bgr, config=config, fps=fps)

    def write(self, frame_bgr):
        """
        Écrit une frame si l'enregistrement est actif.
        """
        if not self.is_recording or self.writer is None:
            return

        h, w = frame_bgr.shape[:2]

        if self.frame_size is None:
            return

        expected_w, expected_h = self.frame_size

        if (w, h) != (expected_w, expected_h):
            frame_bgr = cv2.resize(
                frame_bgr,
                self.frame_size,
                interpolation=cv2.INTER_AREA,
            )

        self.writer.write(frame_bgr)

    def close(self):
        """
        Fermeture propre.
        """
        self.stop()