# -*- coding: utf-8 -*-
"""
LiveEngine : orchestration de la chaine de calcul live, SANS dependance UI.

Encapsule exactement les memes appels que le main OpenCV d'origine
(acquisition -> buffer -> CSM -> beamforming -> overlay) derriere un simple
`step()`. Aucune logique de calcul n'est modifiee ici.

- Construction robuste : repli sur des valeurs/sources synthetiques si la
  calibration, la geometrie, la carte MU32 ou la camera sont indisponibles
  (ou via les flags YAML force_sim_audio / force_sim_camera).
- Aucune importation Qt : ce module est testable et reutilisable tel quel.
"""

import time

import numpy as np
import cv2

from src.live.acquisition_mu32 import MU32Acquisition
from src.live.audio_buffer import SlidingAudioBuffer
from src.live.camera import LiveCamera
from src.live.projection import CameraBFProjection
from src.live.live_state import LiveState
from src.live.overlay import AcousticOverlayRenderer
from src.live.recorder import LiveRecorder

from src.live.live_processing import (
    compute_live_csm,
    compute_mean_level_db,
    is_beamforming_active,
    compute_beamforming_map,
)

from src.live.setup import (
    load_camera_calibration,
    compute_theta_grid_from_camera,
    load_microphone_geometry,
)

from src.live.sim_sources import SimAudioSource, SimCameraSource


class LiveEngine:
    """Chaine de calcul live + un pas `step()`, sans aucune UI."""

    def __init__(self, config):
        self.config = config

        K, dist = self._load_calibration()

        self.w = int(config.cam_w)
        self.h = int(config.cam_h)

        self.theta, self.theta_max = compute_theta_grid_from_camera(config, K)
        self.phi = config.phi

        self.geo_positions = self._load_geometry()

        # ----- Audio -----
        self.sim_audio = bool(getattr(config, "force_sim_audio", False))
        self.state = LiveState(config)
        self.state.recorder = LiveRecorder()
        self.audio = self._start_audio()

        # ----- Camera -----
        self.sim_camera = bool(getattr(config, "force_sim_camera", False))
        self.camera, newK = self._start_camera(K, dist)

        # ----- Pipeline d'affichage -----
        self.projection = CameraBFProjection(
            config=config, newK=newK, w=self.w, h=self.h,
            theta=self.theta, phi=self.phi, theta_max=self.theta_max,
        )
        self.audio_buffer = SlidingAudioBuffer(config.win_samp)
        self.overlay = AcousticOverlayRenderer(
            config=config, projection=self.projection,
            theta=self.theta, phi=self.phi,
        )

    # ----- construction robuste -----
    def _load_calibration(self):
        try:
            return load_camera_calibration(self.config)
        except Exception as exc:
            print(f"[WARN] Calibration camera indisponible ({exc}). "
                  f"[SIM] Matrice K synthetique.")
            w, h = int(self.config.cam_w), int(self.config.cam_h)
            f = float(w)  # focale approx ~ largeur (FOV ~ 53 deg)
            K = np.array([[f, 0, w / 2.0],
                          [0, f, h / 2.0],
                          [0, 0, 1.0]], dtype=np.float64)
            dist = np.zeros((5, 1), dtype=np.float64)
            return K, dist

    def _load_geometry(self):
        try:
            return load_microphone_geometry(self.config)
        except Exception as exc:
            print(f"[WARN] Geometrie micros indisponible ({exc}). "
                  f"[SIM] Grille 4x8 synthetique.")
            xs = (np.arange(8) - 3.5) * 0.03
            ys = (np.arange(4) - 1.5) * 0.03
            gx, gy = np.meshgrid(xs, ys)
            return np.stack(
                [gx.ravel(), gy.ravel(), np.zeros(32)], axis=1
            ).astype(np.float64)

    def _start_audio(self):
        if self.sim_audio:
            print("[SIM] Source audio synthetique (force_sim_audio).")
            src = SimAudioSource(self.config, self.geo_positions, self.state)
            src.start()
            return src
        try:
            src = MU32Acquisition(sampling_rate=self.config.Fe, verbose=False)
            src.start()
            print("[INFO] Acquisition MU32 demarree.")
            return src
        except Exception as exc:
            print(f"[WARN] Carte MU32 absente ou erreur ({exc}). "
                  f"[SIM] Bascule en audio synthetique.")
            self.sim_audio = True
            src = SimAudioSource(self.config, self.geo_positions, self.state)
            src.start()
            return src

    def _start_camera(self, K, dist):
        if self.sim_camera:
            print("[SIM] Camera synthetique (force_sim_camera).")
            cam = SimCameraSource(self.config, K)
            cam.start()
            return cam, cam.newK
        try:
            cam = LiveCamera(self.config, K, dist)
            cam.start()
            print("[INFO] Camera demarree.")
            return cam, cam.newK
        except Exception as exc:
            print(f"[WARN] Camera absente ou erreur ({exc}). "
                  f"[SIM] Bascule en image synthetique.")
            self.sim_camera = True
            cam = SimCameraSource(self.config, K)
            cam.start()
            return cam, cam.newK

    def set_window(self, Tw, Th, delta_f=None):
        """
        Change (Tw, Th[, delta_f]) a chaud (mode Lent/Normal/Rapide).

        Recalcule win_samp / hop_samp et recree le buffer glissant (il se
        remplit a nouveau). Si delta_f est fourni, met aussi a jour la
        resolution d'analyse (lu directement par MIScalc, donc pris en compte
        a la frame suivante). Steering inchange (il ne depend que de f_center).
        """
        cfg = self.config
        cfg.Tw = float(Tw)
        cfg.Th = float(Th)
        if delta_f is not None:
            cfg.delta_f = float(delta_f)
        cfg.win_samp = int(round(cfg.Tw * cfg.Fe))
        cfg.hop_samp = int(round(cfg.Th * cfg.Fe))
        self.audio_buffer = SlidingAudioBuffer(cfg.win_samp)

    # ----- un pas de boucle (identique a l'original, sans affichage) -----
    def step(self):
        config = self.config
        state = self.state

        t_cam0 = time.perf_counter()
        und = self.camera.read_undistorted()
        if und is None:
            # camera deconnectee en cours de route -> image noire (pas de crash)
            und = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        cam_ms = (time.perf_counter() - t_cam0) * 1000.0

        # NB : read_block est l'attente "temps reel" (pacing) -> exclue du calcul.
        block = self.audio.read_block(duration=config.Th)
        self.audio_buffer.push(block)

        t_compute0 = time.perf_counter()
        bf_active = False
        Lp_mean = 0.0
        f_real = None
        csm_ms = bf_ms = ov_ms = 0.0

        if not self.audio_buffer.ready:
            blended = und.copy()
        else:
            t_csm0 = time.perf_counter()
            sigbuf = self.audio_buffer.get_window_channels_first() / config.SMEMS
            MISin, f_real = compute_live_csm(sigbuf, config, state.f_center)
            Lp_mean = compute_mean_level_db(MISin, config)
            csm_ms = (time.perf_counter() - t_csm0) * 1000.0
            bf_active = is_beamforming_active(Lp_mean, config)

            blended = und.copy()

            if bf_active:
                t_bf0 = time.perf_counter()
                WB_lin = compute_beamforming_map(
                    algorithm=state.algorithm, f_center=state.f_center,
                    MISin=MISin, theta=self.theta, phi=self.phi,
                    geo_positions=self.geo_positions, config=config, state=state,
                )
                bf_ms = (time.perf_counter() - t_bf0) * 1000.0

                map_max_lin = float(np.max(WB_lin) + config.eps_lin)
                state.last_map_max_db = 10.0 * np.log10(
                    map_max_lin / (config.p_ref ** 2))
                state.last_map_min_db = state.last_map_max_db - state.dyn_dB

                t_ov0 = time.perf_counter()
                blended = self.overlay.render(
                    image_bgr=und, WB_lin=WB_lin, dyn_dB=state.dyn_dB,
                    alpha_scale=state.alpha_scale, alpha_gamma=state.alpha_gamma,
                    use_turbo=state.use_turbo, show_max=state.show_max,
                )
                ov_ms = (time.perf_counter() - t_ov0) * 1000.0
            else:
                state.last_map_max_db = None
                state.last_map_min_db = None

        if config.mirror_display:
            blended = cv2.flip(blended, 1)

        state.update_fps()
        # NB : l'enregistrement video est laisse a l'UI, qui enregistre ce
        # qu'elle AFFICHE (image centrale en Qt, dashboard complet en OpenCV).

        # Temps "occupe" hors attente audio (camera + calcul) : sert a juger si
        # un mode est tenable (busy < Th) -> faisabilite des modes dans l'UI.
        busy_ms = cam_ms + (time.perf_counter() - t_compute0) * 1000.0

        return blended, {
            "bf_active": bf_active,
            "Lp_mean": Lp_mean,
            "f_real": f_real,
            "ready": self.audio_buffer.ready,
            "filled": self.audio_buffer.filled,
            "busy_ms": busy_ms,
            "cam_ms": cam_ms,
            "csm_ms": csm_ms,
            "bf_ms": bf_ms,
            "ov_ms": ov_ms,
        }

    def close(self):
        try:
            self.state.recorder.close()
        except Exception:
            pass
        for obj in (self.camera, self.audio):
            try:
                obj.close()
            except Exception:
                pass
