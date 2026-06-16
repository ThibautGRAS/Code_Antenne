#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Fonctions et classes génériques bas-niveau pour contrôler la communication USB avec les systèmes Megamicros.
"""


# import os.path as path
import ctypes
import libusb1
import numpy as np


LIBUSB_RECIPIENT_DEVICE = 0x00
LIBUSB_REQUEST_TYPE_VENDOR = 0x02 << 5
LIBUSB_ENDPOINT_OUT = 0x00
LIBUSB_TRANSFER_TIMED_OUT = 2

LIBUSB_TRANSFER_COMPLETED = libusb1.LIBUSB_TRANSFER_COMPLETED
LIBUSB_TRANSFER_CANCELLED = libusb1.LIBUSB_TRANSFER_CANCELLED

TIMEOUT = 6000
NULL = None
MAX_N_PACKET = np.iinfo(int).max   # soit 9223372036854775807 paquets

CMPFUNC = ctypes.CFUNCTYPE(NULL, libusb1.libusb_transfer_p)


def check_n_tdf(n_pkt, n_tdf):
    """Vérifie si le nombre de transferts est compatible avec le nombre de paquets à transmettre.

    Args:
        n_pkt (int): nombre de paquets attendus
        n_tdf (int): nombre de transferts

    Returns:
        (int): nombre de transferts optimal
    """
    if n_pkt < 4 * n_tdf:
        if n_pkt == 1:
            return n_pkt
        else:
            return np.max((n_pkt // 4, 1))
    else:
        return n_tdf


class USB():

    version = None
    """Retourne la version de l'USB utilisée"""

    LIBUSB_SUCCESS = libusb1.LIBUSB_SUCCESS

    def __init__(self, vid, pid, addr, verbose=False):
        """Classe générique pour la communication USB avec les systèmes Megamicros.

        Args:
            vid (str): Vendor ID du système
            pid (str): Product ID du système
            addr (str): adresse logique "endpoint"
            verbose (bool, optional): Passage en mode verbeux. Par défaut `verbose = False`
        """
        self.vid = vid
        self.pid = pid
        self.addr = addr
        self.verbose = verbose

        self.n_tdf = None # nb de tache de fond
        self.num_pkt = None     # id du paquet courant
        self.n_pkt = None       # nombre de paquet total
        self.s_pkt = None       # taille des paquets
        self.s_l_pkt = None     # taille du dernier paquet
        self.last_pkt = None    # = 1 si acquisition du dernier paquet en cours
        self.BBUFFER = None     # buffer principal
        self.transfers = {}     # dictionnaire d'objets qui contiennent des infos sur les mini buffers

        # ouverture de la liaison USB avec le module Mm
        if self.verbose:
            print("* Begin of USB context *")
        libusb1.libusb_init(NULL)
        libusb1.libusb_set_debug(NULL, 3)
        self.handle = None
    
    def __del__(self):
        libusb1.libusb_exit(NULL)
        if self.verbose:
            print("* End of USB context *")

    def open_handle(self):
        """Ouvre la communication USB avec le système d'acquisition.
        """
        self.handle = libusb1.libusb_open_device_with_vid_pid(NULL, self.vid, self.pid)
        err = libusb1.libusb_claim_interface(self.handle, 0)
        if err == 0:
            self.status_usb = True
            if self.verbose:
                print("* USB link opened *")
    
    def close_handle(self):
        """Ferme la communication USB avec le système d'acquisition.
        """
        libusb1.libusb_release_interface(self.handle, 0)
        libusb1.libusb_close(self.handle)
        if self.verbose:
            print("* USB link closed *")

    def status_handle(self):
        """Retourne l'état de la boucle interne pour la gestion des évènements.

        Returns:
            (int): état de la boucle interne
        """
        return libusb1.libusb_handle_events(NULL)
    
    def init_transfers(self, count, count_per_channel, s_pkt, n_tdf, callback=None):
        """Définit les paramètres pour l'initialisation des transferts.

        Args:
            addr (str): adresse logique "endpoint" du système d'acquisition
            count (int): nombre d'échantillons à acquérir
            s_pkt (int): taille de chaque paquet
            n_pkt (int): nombre de paquets à transmettre
            n_tdf (int): numbre de transferts à initialiser
            callback (func, optional): Fonction à appeler à chaque transfert. Par défaut 'callback = None`
        """
        # --- Inputs
        self.count = count
        self.count_per_channel = count_per_channel
        self.s_pkt = s_pkt

        # --- Calculated parameters
        if count <= 0:
            self.n_pkt = MAX_N_PACKET
            self.s_l_pkt = 0
        else:
            self.n_pkt = np.ceil(count / s_pkt).astype(int)
            self.s_l_pkt = int(count % s_pkt)
        self.n_tdf = check_n_tdf(self.n_pkt, n_tdf)
        
        # --- Indices
        self.num_pkt = 0
        self.last_pkt = 0

        # --- Memory buffers parameters
        # self.BBUFFER = ctypes.create_string_buffer(int(self.n_tdf * self.s_pkt))  # buffer principal
        # self.bbuffer_p = {}
        # for i in range(self.n_tdf):
        #     self.bbuffer_p[i] = ctypes.addressof(self.BBUFFER) + i * self.s_pkt
        self.__init_transfers_buffer()
        self.callback_c = CMPFUNC(callback)

    def __init_transfers_buffer(self):
        """Initialize the transfers and the associated buffers of data.
        """
        self.bbuffer_p = {}
        for i in range(self.n_tdf):
            buffer = bytearray(self.s_pkt)
            transfer_buffer = (ctypes.c_char * self.s_pkt).from_buffer(buffer)
            self.bbuffer_p[i] = {"buffer": buffer, "transfer_buffer": transfer_buffer}

    def run_transfers(self):
        if self.verbose:
            print("* Run transfers *")
        for i in range(self.n_tdf):
            self.transfers[i] = libusb1.libusb_alloc_transfer(0)
            libusb1.libusb_fill_bulk_transfer(
                self.transfers[i], self.handle, self.addr, self.bbuffer_p[i]['transfer_buffer'], 
                self.s_pkt,
                self.callback_c, i + 1, TIMEOUT
            )
            self.submit_transfer(self.transfers[i])
    
    def get_transfer_buffer(self, transfer_i):
        """Return the buffer of the current transfer.

        Parameters
        ----------
        transfer_i : USB-transfer object
            Current transfer

        Returns
        -------
        buffer
            Buffer of the current transfer
        """
        buffer = self.bbuffer_p[transfer_i.contents.user_data - 1]["buffer"]
        return buffer[:transfer_i.contents.actual_length]

    @staticmethod
    def submit_transfer(transfer_i):
        """Lance le transfert courant.

        Args:
            transfer_i (libusb1.transfer_p): the current transfer
        """
        retour = libusb1.libusb_submit_transfer(transfer_i)
        if retour:
            print("Erreur " + str(retour) + " au lancement du paquet" + transfer_i)

    def resubmit_transfer(self, transfer_i):
        """Relance (ou pas) le transfert courant.

        Args:
            transfer_i (libusb1.transfer_p): the current transfer
        """
        id_futur = self.num_pkt + self.n_tdf
        if id_futur <= self.n_pkt - 1:
            # --- 1) le paquet sera un paquet (normal) dans la liste : on relance le transfert
            self.submit_transfer(transfer_i)
        else:
            # --- 2) le paquet ne sera pas un paquet de la liste : on ne relance pas le transfert
            pass

    def free_transfers(self):
        """Vide le buffer pour l'ensemble des transferts.
        """
        for i in range(self.n_tdf):
            ''' force l'arrêt du transfert et libère les paquets'''
            self.free_transfer(self.transfers[i])

    @staticmethod
    def free_transfer(transfer_i):
        """Vide le buffer du transfert courrant
        """
        libusb1.libusb_free_transfer(transfer_i)
    
    def cancel_transfers(self):
        """Annule l'ensemble des transferts.
        """
        for i in range(self.n_tdf):
            ''' force l'arrêt du transfert et libère les paquets'''
            self.cancel_transfer(self.transfers[i])
    
    @staticmethod
    def cancel_transfer(transfer_i):
        """Annule le transfert courrant
        """
        libusb1.libusb_cancel_transfer(transfer_i)

    def is_completed(self, transfer_i):
        """Teste si le transfert courant est bien executé.

        Args:
            transfer_i (libusb1.transfer_p): transfert courant
        """
        if transfer_i.contents.status != LIBUSB_TRANSFER_COMPLETED :
            if transfer_i.contents.status != LIBUSB_TRANSFER_CANCELLED:
                if transfer_i.contents.status == LIBUSB_TRANSFER_TIMED_OUT:
                    print ("TIMEOUT lors du transfert du paquet" + str(self.num_pkt + 1))
                else:
                    print ("Erreur lors du transfert du paquet " + str(transfer_i.contents.status))
                #libusb1.libusb_cancel_transfer(transfer_i)
                return False
        else:
            return True

    @staticmethod
    def is_canceled(transfer_i):
        """Teste si le transfert courant est bien annulé.
        
        Args:
            transfer_i (libusb1.transfer_p): transfert courant
        """
        return transfer_i.contents.status == LIBUSB_TRANSFER_CANCELLED

    def are_canceled(self):
        """Teste si tous les transferts sont bien annulés.
        """
        return [self.is_canceled(self.transfers[i]) for i in range(self.n_tdf)]


class USB2(USB):
    """(Déprécié) Classe spécifique pour la gestion de l'USB2.
    """

    version = 2

    def __init__(self, vid, pid, addr, verbose=False):
        super().__init__(self, vid, pid, addr, verbose=False)
        self.version = 2
        print("""This class is implemented to support the compatibility with existing USB2-based devices.
    It tends to be depreciated in the future.
    Please try to use a USB3-based device, which provides more stable capabilities.""")

    def write_command(self, request, data_ptr, length):
        """
        fonction qui envoie une commande de controle vers USB2

        :param request: signature du commande controle
        :param data_ptr: data du commande controle
        :param length: taille de data_ptr
        :return:
        """
        typerequest = self.LIBUSB_RECIPIENT_DEVICE | self.LIBUSB_REQUEST_TYPE_VENDOR | self.LIBUSB_ENDPOINT_OUT
        value = 0
        index = 0
        if (length == 0):
            dat = b'\x00'
            dbg = libusb1.libusb_control_transfer(self.handle, typerequest, request, value, index, dat, 1, self.TIMEOUT)
            assert dbg == 1
        else:
            dbg = libusb1.libusb_control_transfer(self.handle, typerequest, request, value, index, data_ptr, length,
                                                  self.TIMEOUT)
            assert dbg == length


class USB3(USB):
    """Classe spécifique pour la gestion de l'USB3.
    """

    version = 3
    
    def write_command(self, request, data_ptr, length):
        """Envoie une commande de controle via protocole USB.

        Args:
            request (str): requête logique
            data_ptr (str): données binaires à transmettre
            length (str): taille des données binaires à transmettre
        """
        typerequest = LIBUSB_RECIPIENT_DEVICE | LIBUSB_REQUEST_TYPE_VENDOR | LIBUSB_ENDPOINT_OUT
        value = 0
        index = 0
        dbg = libusb1.libusb_control_transfer(
            self.handle, typerequest, request, value, index, data_ptr, length, TIMEOUT)
        assert dbg == length
