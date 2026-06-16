# -*- coding: utf-8 -*-
"""
Acquisition live avec carte Megamicros MU32.
"""

import numpy as np

from src.megamicros import allowed_devices, System


class MU32Acquisition:
    def __init__(self, sampling_rate: int, verbose: bool = False):
        self.sampling_rate = sampling_rate
        self.verbose = verbose
        self.system = None

    def start(self):
        """
        Initialise et démarre l'acquisition MU32 en mode interactif.
        """
        mm_args = allowed_devices["32"]["usb3"]

        mems = np.ones((4, 8), bool)
        va = np.zeros((4,), bool)

        self.system = System(**mm_args, verbose=self.verbose)

        self.system.set_parameters(
            filename=None,
            mems=mems,
            va=va,
            vl=0,
            cpt=1,
            samplingrate=self.sampling_rate,
            interactif=True,
        )

        self.system.start(duration=0, blocking=False)

    def read_block(self, duration: float):
        """
        Lit un bloc temporel.

        Parameters
        ----------
        duration : float
            Durée d'acquisition en secondes.

        Returns
        -------
        block : ndarray, shape (Nsamp, Nch)
            Bloc audio sans la colonne compteur.
        """
        if self.system is None:
            raise RuntimeError("MU32Acquisition non démarrée. Appeler start() avant read_block().")

        data_and_cpt = self.system.get_data(duration=duration)

        # Suppression de la colonne compteur
        block = data_and_cpt[:, 1:].astype(np.float64)

        return block

    def close(self):
        """
        Arrête et ferme proprement la carte MU32.
        """
        if self.system is None:
            return

        try:
            self.system.stop()
            self.system.join()
            self.system.close()
        except Exception:
            pass

        self.system = None