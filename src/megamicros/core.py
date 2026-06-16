#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
Fonctions et classes génériques pour contrôler les systèmes d'acquisition Megamicros.
"""


import collections
import os.path as osp
import types
import ctypes
import struct
import time
import numpy as np
from pydispatch import Dispatcher
from .usb import USB2, USB3
from .io import File, detect_extension


allowed_devices = {
    '32':{
        'usb2': dict(version=32, version_usb=2, vid=0xFE27, pid=0xAC00, addr=0x82),
        'usb3': dict(version=32, version_usb=3, vid=0xFE27, pid=0xAC03, addr=0x81),
    },
    '128':{
        'usb2': dict(version=128, version_usb=2, vid=0xFE27, pid=0xAC00, addr=0x82),
    },
    '256':{
        'usb3': dict(version=256, version_usb=3, vid=0xFE27, pid=0xAC01, addr=0x81),
    },
    '1024':{
        'usb3': dict(version=1024, version_usb=3, vid=0xFE27, pid=0xAC02, addr=0x81),
    },
}

MAX_SIZE_BUFFER = 2
MAX_DURATION_POSSIBLE = np.iinfo(int).max   # 2924712086.7753601074 siècles

# Generic commands for any devices
C_START = 0x02
C_STOP = 0x03
T_SOFT = 0x00
T_TRIG1 = 0x01
T_TRIG2 = 0x02


def clockdiv2rate(clockdiv):
    """Convert from intern clock to samplingrate.

    Args:
        clockdiv (int): horloge interne des capteurs MEMS (5 <= clockdiv < 15)
    
    Returns:
        int: fréquence d'échantillonnage (en Hertz)
    """
    return 500000 // (clockdiv + 1)


def rate2clockdiv(samplingrate):
    """Convert from samplingrate to intern clock.

    Args:
        samplingrate (int): fréquence d'échantillonnage (en Hertz)

    Returns:
        (int): horloge interne des capteurs MEMS (5 <= clockdiv < 15)
    """
    return 500000 // samplingrate - 1


class MegamicrosError(Exception):
    """Class for Megamicros exceptions"""
    pass


class MegamicrosWarning(Warning):
    """Class for Megamicros warnings"""
    pass


class Megamicros(Dispatcher):
    """Classe générique Megamicros pour gestion des évènements.
    """

    _events_ = ["new_data"]

    def __init__(self, version=None, vid=None, pid=None, addr=None, version_usb=3, verbose=False):
        """Initialisation de la classe Megamicros.

        Args:
            version (int): nombre de voies MEMS
            vid (str): vendor ID propre au système d'acquisition
            pid (str): product ID propre au système d'acquisition
            addr (str): adresse logique "endpoint"
            version_usb (int, optional): Version du module USB du système d'acquisition. Par défault `version_usb=3`.
            verbose (bool, optional): Passage en mode verbeux. Par défaut `verbose=False`
        """
        self.initialize(version, vid, pid, addr, version_usb, verbose)
    
    def initialize(self, version=None, vid=None, pid=None, addr=None, version_usb=3, verbose=False):
        """Initialisation de la classe Megamicros."""
        self.version = version
        self.addr = addr
        if version_usb == 2:
            self.usbh = USB2(
                vid=vid, pid=pid, addr=addr, verbose=verbose,
            )
        elif version_usb == 3:   # choix automatique du module USB3
            self.usbh = USB3(
                vid=vid, pid=pid, addr=addr, verbose=verbose,
            )
        else:
            self.usbh = None
        self.verbose = verbose
    
    def open_link_usb(self):
        """Ouvre la communication USB avec le système.
        """
        self.usbh.open_handle()
    
    def close_link_usb(self):
        """Ferme la communication USB avec le système.
        """
        self.usbh.close_handle()

    def set_parameters(self, mems, va, cpt, vl=0,
        buffer_duration=0.250, samplingrate=50000,   
        n_tdf=8, dtype="int32",
        filename=None, interactif=False):
        """Définit les paramètres utilisateurs propres à l'acquisition.

        Args:
            mems (np.array): masque des microphones actifs (= 1) ou non (= 0)
            va (np.array): masque des voies analogiques actives (= 1) ou non (= 0)
            cpt (np.array): utilisation d'un compteur (= 1) ou non (= 0)
            vl (np.array, optional): masque des voies logiques actives (= 1) ou non (= 0). Par défaut `vl = 0`
            buffer_duration (float, optional): taille du buffer temporaire (en secondes). Par défaut `buffer_duration = 0.250`
            samplingrate (int, optional): fréquence d'échantillonnage. Par défaut `samplingrate = 50000`
            n_tdf (int, optional): nombre de tâches de fonds pour les transferts USB. Par défaut `n_tdf = 8`
            dtype (str, optional): Format des données acquises par le système. Par défaut `dtype = int32`
            filename (str, optional): Nom du fichier de sauvegarde. Si `interactif` vaut `None`, `filename` vaut `None`. Par défaut `filename = test.dat'
            interactif (bool, optional): Active ou non le mode intéractif. Par défaut `interactif = False`
        """
        # --- Paramètres canaux d'acquisition
        self.mems = mems
        self.va = va
        self.vl = vl
        self.cpt = cpt
        self.n_beams = len(mems)
        self.nb_voies = np.sum(self.mems) + np.sum(self.va) + np.sum(self.cpt) + np.sum(self.vl)

        # --- Paramètres transfert USB
        self.samplingrate = samplingrate
        self.dtype = dtype
        self.n_tdf = n_tdf
        self.is_on = False
        #self.queue = queue.Queue()
        self.queue = collections.deque()

        # --- Paramètres interactivité
        self.interactif = interactif
        if not interactif:     # Cas d'un enregistrement imposé par l'utilisateur
            self.buffer_duree = None
            #_, ext = detect_extension(filename)
            # if ext == ".h5":
            self.file = File(filename, mode="w")
            # else:
            #     self.file = open(filename, "wb")
        else:                       # Cas d'un mode interactif
            self.buffer_duree = buffer_duration
            self.file = None
        
        # Gestion de l interactivite
        #if self.interactif:
            # duree_ideale_buffer_tmp = int(5 * self.samplingrate * self.nb_voies)  # par defaut 5 sec
            # duree_buffer_tmp = int(int(duree_ideale_buffer_tmp / (self.usbh.s_pkt / 4)) * (self.usbh.s_pkt / 4))
            # self.data_tmp = np.zeros((duree_buffer_tmp, )).astype(np.int32)

            # self.buffer_size = int(buffer_duration * self.samplingrate)
            # self.buffer_size_tot = self.buffer_size * self.nb_voies
            # self.data_ptr = 0
            # self.data_ptr_R = 0
            # self.data_ptr_retour = 0
            # self.last_data_ptr = 0
            
            # # Pour allocation
            # self.data = np.zeros((self.buffer_size, self.nb_voies), dtype=self.dtype)
            # self.tmp = np.zeros((self.buffer_size_tot, ), dtype=self.dtype)

    def set_samplingrate(self, C_INIT=0x01):
        """Définit la fréquence d'échantillonnage du système.

        Args:
            C_INIT (hexadecimal, optional): requête logique. Par défaut `C_INIT = 0x01`.
        """
        clockdiv = rate2clockdiv(self.samplingrate)
        self.usbh.clockdiv = clockdiv

        buf = ctypes.create_string_buffer(16)
        buf[0] = bytes((C_INIT,))
        buf[1] = bytes((clockdiv,))
        self.usbh.write_command(0xB1, buf, 2)

        # sécurité pour l'initialisation des MEMS
        delai = 90 * (clockdiv + 1) // 10
        time.sleep(delai / 1000)
    
    def set_dtype(self):
        """Définit le format des données acquises.
        """
        buf = ctypes.create_string_buffer(16)
        buf[0] = b'\x09'
        if self.dtype == "int32":
            buf[1] = b'\x00' 
        elif self.dtype == "float32":
            buf[1] = b'\x01'
        self.usbh.write_command(0xB1, buf, 2)

    def set_duration(self, duration):
        """Définit la durée d'acquisition du système.

        Args:
            duration (float): durée d'acquisition (en secondes)
        """
        assert self.usbh is not None, "Aucune instance USB !"
        self.duration = duration

        if self.nb_voies < 1024 and self.nb_voies > 256:
            coeff = int(1024 // self.nb_voies)
        elif self.nb_voies < 256 and self.nb_voies > 128:
            coeff = int(256 // self.nb_voies)
        elif self.nb_voies < 128:
            coeff = int(128 // self.nb_voies)
        if duration <= 0:
            # --- Infinite recording duration
            count_per_channel = int(0)
            count = int(0)
            # s_pkt = 1024 * np.sum(self.mems)
            s_pkt = 1024 * self.nb_voies
        else:
            # --- Finite recording duration
            count_per_channel = int(duration * self.samplingrate)
            count = int(4 * self.nb_voies * count_per_channel)
            #print(f"coeff{type(coeff)}, count {type(count)} et count_per_channel {type(count_per_channel)}")
            s_pkt = coeff * 256 * count // count_per_channel
        # s_pkt = 1024*1024
        # s_pkt = 512*1024
        
        print(f"s_pkt {s_pkt}")
        self.usbh.init_transfers(
            count = int(count),
            count_per_channel = int(count_per_channel),
            s_pkt = int(s_pkt),
            n_tdf = self.n_tdf,
            callback = self.transfer_callback_py,
        )
        self.set_count()
        # Open the datatable in H5/HDF5
        #print(50*'=-')
        #print(self.file.filename)
        # if ".dat" not in self.file.filename:
        if not self.interactif:
            self.file.open(size=count, dtype=self.dtype)
    
    def set_count(self, C_COUNT=0x04):
        """Définit le nombre d'échantillons par voie à acquérir.
        """
        # tester si "int16" ou "int32"
        c = int(self.usbh.count_per_channel)
        # teste si "c == 0" ?
        buf = ctypes.create_string_buffer(16)
        buf[0] = bytes((C_COUNT,))
        buf[1] = bytes((c & 0x000000ff,))
        buf[2] = bytes((((c & 0x0000ff00) >> 8),))
        buf[3] = bytes((((c & 0x00ff0000) >> 16),))
        buf[4] = bytes((((c & 0xff000000) >> 24),))
        # verifier si le vecteur est vide
        self.usbh.write_command(0xB4, buf, 5)

    def turn_on_channels(self):
        """Met en marche l'alimentation des microphones MEMS.
        """
        if self.verbose:
            print("* Turn on channels *")
        self._select_channels()
        
        page_txt=[bytes((x,)) for x in range(self.n_beams)]
        page_txt.append(b'\xFF')

        buf = ctypes.create_string_buffer(16)
        for i in range(len(page_txt)):
            buf[0] = b'\x05'            # commande active
            buf[1] = b'\x00'            # module (static, TO NOT MODIFY)
            buf[2] = page_txt[i]        # Page
            buf[3] = self.page[i]       # micros actifs
            self.usbh.write_command(0xB3, buf, 4)
        time.sleep(2)

    def _select_channels(self, nb_micros=8):
        """Active les voies pour lesquels il y a des données a récupérer.

        Args:
            nb_micros (int, optional): nombre de microphones par faisceau. Par défaut `nb_micros = 8`
        """
        self.page = {}
        # Setup MEMS pages:
        for i in range(self.n_beams):
            ipage = 0
            for chnl in range(nb_micros):
                ipage += self.mems[i][chnl] << chnl
            self.page[i] = struct.pack('B', ipage)

        # --- Version 32, 128, 256
        if self.version < 1024:
            # Setup VA and count page:
            ipage = (self.va[0] << 0) + \
                    (self.va[1] << 1) + \
                    (self.va[2] << 2) + \
                    (self.va[3] << 3) + \
                    (self.vl << 6) + \
                    (self.cpt << 7)
            self.page[self.n_beams] = struct.pack('B', ipage)
        # --- Version 1024
        else:
            cont = 0
            for k in range(4):
                 # Setup VA and count page:
                vl = int(self.vl[k])
                cpt = int(self.cpt[k])
                ipage = (self.va[cont] << 0) + \
                        (self.va[cont+1] << 1) + \
                        (self.va[cont+2] << 2) + \
                        (self.va[cont+3] << 3) + \
                        (int(self.vl[k]) << 6) + \
                        (int(self.cpt[k]) << 7)
                self.page[252+k] = struct.pack('B', ipage)
                cont = cont + 1

    def run(self, trig=0, callbacks=[]):
        """Lance le processus d'acquisition.

        Args:
            trig (int, optional): Active ou non le mode trigger :
                - "0" : déclenchement direct
                - "1" : déclenchement via entrée sur TRIG_1
                - "2" : déclenchement via entrée sur TRIG_2
            Par défaut `trig=0` ("soft").
        """
        
        self.set_callbacks(callbacks)
        
        self.usbh.run_transfers()

        buf = ctypes.create_string_buffer(16)
        buf[0] = bytes((C_START,))
        # IL FAUT DECALER LES DIGITS POUR DECLENCHER LE FRONT
        # (valeur trig) + ((valeur front) << 6)
        if trig == 1:
            buf[1] = bytes((T_TRIG1,))
        elif trig == 2:
            buf[1] = bytes((T_TRIG2,))
        elif trig == 0:
            buf[1] = bytes((T_SOFT,))
        self.usbh.write_command(0xB1, buf, 2)

        print('* Acquisition en cours... (%s)*\n' % time.ctime().split(' ')[-2])

    def set_callbacks(self, callbacks):
        """Définit les fonctions appelées à chaque transfert en mode intéractif. 
        Pour fonctionner, le flag `interactif` doit valoir `True`.

        Args:
            callbacks (list): Liste des fonctions ou des classes à appeler
        """
        for callback in callbacks:
            if isinstance(callback, (type, types.FunctionType)):
            # --- C'est une fonction
                self.bind(new_data=callback)
            else:
            # --- C'est une classe
                if hasattr(callback, 'receive'):
                # --- On vérifie qu'elle contient la fonction `receive`
                    self.bind(new_data=callback.receive)
                else:
                    if self.verbose:
                        print("* No function `receive` found !*")
                        continue
                if self.verbose:
                    print("* Add a callback ! *")
    
    def is_running(self):
        """Retourne l'état de la gestion des évènements.
        """
        return (self.usbh.status_handle() == self.usbh.LIBUSB_SUCCESS) and (self.usbh.num_pkt < self.usbh.n_pkt)

    def transfer_callback_py(self, transfer_i):
        """Fonction callback générique, appelée à chaque transfert.
        
        Args:
            transfer_i (libusb1.transfer_p): Transfert actuel
        """
        if self.verbose:
            print("Callback, num_pkt = %d / %d" % (self.usbh.num_pkt + 1, self.usbh.n_pkt))
        # --------------------------------------------------------------------------------------------------
        # 1 le transfert s est mal passe
        # --------------------------------------------------------------------------------------------------
        if not self.usbh.is_completed(transfer_i):
            self.usbh._cancel_transfer(transfer_i)
        
        # --------------------------------------------------------------------------------------------------
        # 2 le transfert s est bien passe
        # --------------------------------------------------------------------------------------------------
        else:
            # ++++++++++++++++++++++++++++++++++++++++++
            # 2.1 Sauvegarde des donnees sur le disque dur
            # ++++++++++++++++++++++++++++++++++++++++++
            if not self.interactif:
                self.to_file(transfer_i)
            else:
                self.to_buffer(transfer_i)
                #for callback in self.callbacks:
                #    callback()
            # ++++++++++++++++++++++++++++++++++++++++++
            # 2.2 Relance des transferts
            # ++++++++++++++++++++++++++++++++++++++++++
            self.usbh.resubmit_transfer(transfer_i)
            # ++++++++++++++++++++++++++++++++++++++++++
            # 2.3 On incremente le nombre de paquets traites
            # ++++++++++++++++++++++++++++++++++++++++++
            self.usbh.num_pkt += 1
    
    def to_file(self, transfer_i):
        if transfer_i.contents.actual_length == transfer_i.contents.length:
            # 2.1.1 Cas standard => le paquet recu est un paquet de longueur normale
            if self.verbose:
                print("---> paquet longueur normale !!")
            if self.usbh.num_pkt == self.usbh.n_pkt - 2:
                self.usbh.last_pkt
        else:
            # 2.1.2 Cas particulier  => le paquet recu n'est pas un paquet de longueur normale
            #               c'est le dernier paquet de la liste avec une longueur self.s_l_pkt
            if self.verbose:
                print("---> paquet longueur reduite")
        data = self.usbh.get_transfer_buffer(transfer_i)
        #if not ".dat" in self.file.filename:
        #    data = np.frombuffer(data, np.int32)
        self.file.write(data)

    def to_buffer(self, transfer_i):
        """Transfère le contenu du buffer courant dans le tampon

        :return:
        """
        if transfer_i.contents.actual_length == transfer_i.contents.length:
            # 2.1.1 Cas standard => le paquet recu est un paquet de longueur normale
            if self.verbose:
                print("---> paquet longueur normale ??")
            # --- TO DO : NEW WAY TO PACKET END
            # if self.usbh.num_pkt == self.usbh.n_pkt - 2:
            #     self.usbh.last_pkt
        else:
            # 2.1.2 Cas particulier  => le paquet recu n'est pas un paquet de longueur normale
            #               c'est le dernier paquet de la liste avec une longueur self.s_l_pkt
            if self.verbose:
                print("---> paquet longueur reduite")
        buffer = self.usbh.get_transfer_buffer(transfer_i)
        data = np.frombuffer(buffer, np.int32)
        # self.queue.extend(data[::-1])
        self.queue.extend(data)
        # for item in data:
        #     self.queue.append(item)

    def get_data(self, duration=1):
        """Return a frame of given duration from the buffer.

        Parameters
        ----------
        duration : int, optional
            duration of the extracted frame, by default 1

        Returns
        -------
        data
            an array of recorded data
        """
        n_tixels = int(duration * self.samplingrate)
        size = n_tixels * self.nb_voies
        if len(self.queue) >= 3 * size:
            self.queue.clear()
        while len(self.queue) < size:
            time.sleep(0.1)
        tmp = np.array([self.queue.popleft() for _ in range(size)])

        # if len(self.queue) >= size:
        #     #tmp = np.zeros((size, ), dtype=np.int32)
        #     if self.verbose:
        #         time0 = time.time()
        #     queue_tmp = self.queue.copy()
        #     tmp = np.array([queue_tmp.pop() for _ in range(size)])[::-1]
        #     #self.queue.clear()
        #     del queue_tmp
        #     #for i in range(size):
        #     #    tmp[i] = self.queue.popleft()
        #     #print(tmp)
        #     if self.verbose:
        #         print("Temps lecture :", time.time() - time0)
        return tmp.reshape((n_tixels, self.nb_voies))
        # else:
        #     warnings.warn("Not enough data to return", MegamicrosWarning)
        #     return None

    def send_data(self):
        """Envoie les données aux callbacks déclarées
        """
        size = self.buffer_size_tot
        if self.data_ptr_R + size < self.data_ptr_lenmax:
        # print "donnees contigues"
            if self.data_ptr > self.data_ptr_R + size:
                #res = 1
                #if self.data_ptr_R + size < len(self.data_tmp):
                self.data = self.data_tmp[self.data_ptr_R:self.data_ptr_R + size].reshape((self.buffer_size, self.nb_voies))
                self.emit('new_data', data=self.data.astype(self.dtype))

                self.data_ptr_R = self.data_ptr_R + size
                #return data
            #else:
            #     # print "bloc non pret pour lecture"
            #    return 0
            #     res = 0
        else:
            # print "pb:::::::::"
            size_end = self.last_data_ptr - self.data_ptr_R
            if (size_end + self.data_ptr > size) and (self.data_ptr_retour == 1):
                #tmp1 = self.data_tmp[self.data_ptr_R:self.last_data_ptr]
                #tmp2 = self.data_tmp[0:size - size_end]
                # a optimiser avec np.hstack
                #self.tmp[0:len(tmp1)] = tmp1
                #self.tmp[len(tmp1):] = tmp2
                self.tmp = np.hstack((
                    self.data_tmp[self.data_ptr_R:self.last_data_ptr],
                    self.data_tmp[0:size - size_end],
                ))
                self.data = self.tmp.reshape((self.buffer_size, self.nb_voies))
                self.emit('new_data', data=self.data)  # permet d'activer un 'event' disant 'vient récupérer la donnée' (légitime ?)
                
                self.data_ptr_R = size - size_end
                self.data_ptr_retour = 0
                
                #res = 1
            #else:
            #    return 0
            #     res = 0

    @property
    def parameters(self):
        return dict(
            n_channels=np.sum(self.mems),
            n_analogs=np.sum(self.va),
            counter=self.cpt,
            samplingrate=self.samplingrate,
            dtype=self.dtype,
            duration=self.duration,
        )

    def __str__(self):
        chaine = '\n' + 50 * '='
        chaine = chaine + '' + '\n'
        chaine = chaine + 'Megamicros %s \n' % self.version
        chaine = chaine + '' + '\n'
        chaine = chaine + "Duree d'acquisition : %.1f \n" % self.duration
        chaine = chaine + "Nombre de voies d'acquisition : %d \n" % self.nb_voies
        chaine = chaine + "Nombre d'octets a acquerir : %d \n" % self.usbh.count
        chaine = chaine + "Nombre de paquets : %d \n" % self.usbh.n_pkt
        chaine = chaine + "Nombre de taches de fond : %d \n" % self.usbh.n_tdf
        chaine = chaine + "Taille des paquets : %d \n" % self.usbh.s_pkt
        chaine = chaine + "Taille du dernier paquet : %d \n" % self.usbh.s_l_pkt
        chaine = chaine + 50 * '=' + '\n'
        return chaine

##########################################################################################
class Parameters():
    def __init__(self):
        self.n_beams = 4
        self.nb_va = 0
        self.duration = 1
        self.cpt = 1
        self.tdf = 10
        self.path = '/'
        self.system = '32'
        self.filename = 'toto.dat'
        self.progress = 0
        self.duration_graph = 0.1
        self.voie = 1
        self.interactif = 0
        self.ylim = 0
        self.ymoins = 0
        self.yplus = 1
        self.choix_graph = 'signal'
        self.stop = 0

    def __str__(self):
        res = str(self.n_beams) + '\n'
        res = res + str(self.nb_va) + '\n'
        res = res + str(self.duration) + '\n'
        res = res + self.path + '\n'
        res = res + self.system + '\n'
        res = res + self.filename
        return res


if __name__ == "__main__":
    print(allowed_devices)
