#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Fonctions et classes spécifiques au contrôle des systèmes USB3.
"""


# TODO : 
# - tester la valeur du compteur à la volée
# - tester le nombre d'octet écrit
# - faire un test sur la taille du disque


import ctypes
import time
import threading
import numpy as np
from .core import Megamicros, MegamicrosError, allowed_devices
#from .interactive import PrintData, LiveRecording
from .io import add_date_to_filename

# # Device parameters
# VERSION = 32
# VERSION_USB = 3
# VENDOR_ID = 0xFE27
# PRODUCT_ID = 0xAC03
# ADDR = 0x81

MEMS_PER_BEAM = 8
MEMS_SENSIBILITY = np.sqrt(2) / 420428

# FPGA Command for Megamicros32 USB3
C_RESET = 0x00
C_RESET_FX3 = 0xC0
C_RESET_EXT = 0xC4  # Reset pseudo-hard du FPGA


def alloc_channels(n_channels, n_mems, n_va):
    """Allocate channels to record.

    Parameters
    ----------
    n_channels : int
        total number of channels (32 or 256)
    n_mems : int
        number of MEMS to activate
    n_va : [type]
        number of analog channels to activate

    Returns
    -------
    mems
        boolean array of activated microphone channels
    va
        boolean array of activated analog channels
    """
    mems = np.zeros((n_channels, ), bool)
    va = np.zeros((4, ), bool)
    mems[:n_mems] = 1
    if n_channels != 32:
        va[:n_va] = 1
    return mems.reshape((-1, MEMS_PER_BEAM)), va


class System(Megamicros):
    """Instance pour contrôle des systèmes Megamicros.

    Args:
        Megamicros (class): classe `core.Megamicros` pour inhéritance
    """
    
    is_on = False
    
    def init_FX3(self):
        """Initialisation du module FX3
        """
        buf = ctypes.create_string_buffer(16)
        if self.verbose:
            print("\n* Initialisation FX3  *")
        self.usbh.write_command(
            C_RESET_FX3, buf, 0,
        )
        time.sleep(1)

        # PAS INDISPENSABLE ? à tester
        if self.verbose:
            print("* Initialisation FPGA bas *")
        self.usbh.write_command(
            C_RESET_EXT, buf, 0,
        )
        time.sleep(1)

        if self.verbose:
            print("* Initialisation FPGA *")
        buf[0] = bytes((C_RESET,))
        self.usbh.write_command(0xB0, buf, 1)
        #time.sleep(1)

        # PAS INDISPENSABLE ? à tester
        if self.verbose:
            print("* Initialisation FPGA bas *")
        self.usbh.write_command(
            C_RESET_EXT, buf, 0,
        )
        time.sleep(1)

        # PAS INDISPENSABLE ? à tester
        if self.verbose:
            print("* Initialisation FX3 *\n ")
        self.usbh.write_command(
            C_RESET_FX3, buf, 0,
        )
        time.sleep(1)

    def start(self, duration=1, trig=0, callbacks=[], blocking=True):
        """Déclenche le processus d'acquisition du système.

        Args:
            duration (float, optional): Duree d'enregistrement (en secondes). Par défaut `duration=1`.
            trig (int, optional): Active ou non le mode trigger. Par défaut `trig=0` ("soft").
        """
        # 1ere étape : ouverture du lien USB
        self.open_link_usb()

        # 2ème étape : Initialisation du boiter d'acquisition
        self.init_FX3()
        self.set_samplingrate()
        self.set_dtype()    # A SUPPRIMER POUR L'UTILISATEUR
        self.set_duration(
            duration=duration,
        )
        self.turn_on_channels()

        # 3ème étape : lancer le processus d'acquisition
        self.run(
            trig=trig,
            callbacks=callbacks,
        )
        self.is_on = True

        self.loopback = threading.Thread(target=self.loop_event, daemon=True)
        self.loopback.start()
        if blocking:
            self.loopback.join()
    
    def join(self):
        """Active l'attente de la boucle interne.
        """
        self.loopback.join()

    def loop_event(self):
        """Boucle interne pour la gestion des évènements.
        """
        while self.is_running():
            #self.usbh.status_handle()
            if self.usbh.last_pkt == 1 and self.usbh.version == 2:
                # --- Uniquement pour support USB2
                msg = ctypes.create_string_buffer(16)
                if self.interactif:
                    self.usbh.num_pkt = self.usbh.n_pkt
                self.usbh.cancel_transfers()
                self.usbh.write_command(0xC1, msg, 0)
                break
            else:
                pass
        else:
            self.is_on = False
            return

    def stop(self):
        """Arrêt anticipé imposé par l'utilisateur
        """
        # --- Façon directe d'arrêter l'enregistrement
        print("# --- FORCED STOP BY USER --- #")
        self.usbh.num_pkt = self.usbh.n_pkt - self.usbh.n_tdf
        self.usbh.last_pkt = 1
        self.is_on = False

        #buf = ctypes.create_string_buffer(16)
        #buf[0] = bytes((C_STOP,))
        #buf[1] = bytes((T_SOFT,))
        #self.usbh.write_command(0xB0, buf, 1)

        self.loopback.join()
        time.sleep(1)

    def close(self, message=""):
        """Met fin au processus d'acquisition du système.
        """
        
        self.usbh.free_transfers()
        
        if not self.interactif:
            self.file.dump_log(self.parameters, message=message)
            self.file.close()

        # --- Reset FIFO (par précaution, permet de vider la mémoire du module FX)
        # Possiblement plus nécessaire
        buf = ctypes.create_string_buffer(16)
        buf[0] = bytes((C_RESET,))
        self.usbh.write_command(0xB1, buf, 2)

        self.close_link_usb()



############################


def __run_32(channels, analogs, duration, filename, message, verbose):
    """Fonction de test pour système Megamicros 32 voies USB3

    Args:
        duration (float): duree acquisition
        verbose (bool): mode verbeux
    """
    mm_args = allowed_devices["32"]["usb3"]
    mems, va = alloc_channels(32, channels, analogs)
    Mm = System(
        **mm_args, verbose=verbose,
    )
    Mm.set_parameters(
        filename=filename, samplingrate=50000,
        mems=mems, va=va, vl=0, cpt=1,
        interactif=False,
    )
    try:
        Mm.start(
            duration=duration,
            blocking=True,
        )
    except KeyboardInterrupt:
        Mm.stop()
    finally:
        Mm.close(message=message)
    print(Mm)


def __run_256(channels, analogs, duration, filename, message, verbose):
    """Fonction de test pour système Megamicros 256 voies USB3

    Args:
        duration (float): duree acquisition
        verbose (bool): mode verbeux
    """
    mm_args = allowed_devices["256"]["usb3"]
    mems, va = alloc_channels(256, channels, analogs)
    Mm = System(
        **mm_args, verbose=verbose,
    )
    Mm.set_parameters(
        filename=filename, samplingrate=50000,
        mems=mems, va=va, vl=0, cpt=1,
        interactif=False,
    )
    try:
        Mm.start(
            duration=duration,
            blocking=True,
        )
    except KeyboardInterrupt:
        Mm.stop()
    finally:
        Mm.close(message=message)

    print(Mm)


def run(version, channels, analogs=0, duration=5, filename=None, message="", verbose=False):
    """Run an acquisition with Megamicros system.

    Args:
        version (int) : version of the used system
        channels (int) : number of microphone channels to use
        analogs (int) : number of analog channels to use
        duration (float) : duration of the recording
        filename (str) : name of the stored data file
        message (str) : optional string written in log
        verbose (bool) : run in verbose mode
    """
    # path = add_date_to_filename(filename)
    if version == 32:
        __run = __run_32
    elif version == 256:
        __run = __run_256
    else:
        raise MegamicrosError("Unknown version of the used system !")
    __run(channels=channels, 
        analogs=analogs, 
        duration=duration, 
        filename=filename,
        message=message,
        verbose=verbose)


def _test_simple_callbacks():
    """Fonction de test pour ajout callback

    Args:
        duration (float): duree acquisition
        verbose (bool): mode verbeux
    """

    #h5 = H5File("test.h5")
    pd = PrintData()

    mm_args = allowed_devices["32"]["usb3"]

    mems = np.ones((4, 8), np.bool)
    va = np.zeros((4,), np.bool)

    Mm = System(
        **mm_args, verbose=False,
    )
    Mm.set_parameters(
        filename=None, samplingrate=50000,
        mems=mems, va=va, vl=0, cpt=1,
        interactif=True,
    )
    try:
        Mm.start(
            duration=10,
            callbacks=[pd],
            blocking=True,
        )
    except KeyboardInterrupt:
        Mm.stop()
    finally:
        Mm.close()

    print(Mm)


def _test_interactive_recording():
    
    datapath = "/home/hugo/Documents/Dev/Megamicros/test"

    h5 = LiveRecording(dirpath=datapath)
    h5.open()

    mm_args = allowed_devices["256"]["usb3"]
    print(mm_args)

    mems = np.zeros((32, 8), bool)
    va = np.zeros((4,), bool)
    mems[:2, :] = 1

    Mm = System(
        **mm_args, verbose=False,
    )
    Mm.set_parameters(
        filename=None, samplingrate=50000,
        mems=mems, va=va, vl=0, cpt=1,
        interactif=True,
    )

    try:
        Mm.start(
            duration=5,
            callbacks=[h5],
            blocking=True,
        )
    except KeyboardInterrupt:
        Mm.stop()
        Mm.join()
    finally:
        h5.close_stream()
        h5.close()
        Mm.close()

    print(Mm)

if __name__ == '__main__':
    _test_interactive_recording()
