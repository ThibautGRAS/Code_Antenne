"""Python module to read Siemens LMS .LDSF files

@author: Nicolas Bedouin

Example usage:
import ldsfdatareader as ldsf
with ldsf.open('myfile.ldsf') as f:
    print(f.info)
    ch1 = f['chname1'].series()
    ch1.plot()
    for ch in f.values():
        print(ch.name, ch.series().mean())
"""

__all__ = ['LDSFStatus', 'LDSFFile']
__version__ = '1.0.3'

encoding = 'utf-8'  # default encoding

import io
import os
import collections
import numpy

class LDSFStatus(RuntimeError):
    """Messages d'erreur"""
    errors = ("status OK", 'not a LDSF file', "file cannot open",
            "file already in use", 'file corrupt')

    def __init__(self, value):
        super(LDSFStatus, self).__init__(self.errors[value])


class LDSFFileInfo(object):
    """Métadonnées de base du fichier ldsf"""

    def __init__(self, sample_rate, start_store_time, duration, channel_count, version):
        self.sample_rate = sample_rate # Fréquence d'échantillonnage max.
        self.start_store_time = start_store_time  # Date UTC en datetime
        self.duration = duration  # Durée totale d'enregistrement
        self.channel_count = channel_count # Nombre de voies dans le fichier
        self.version = version   # Version du fichier LDSF

    def __str__(self):
        import pytz
        ici = pytz.timezone('Europe/Paris')
        dt = self.start_store_time.astimezone(ici).strftime('%a %d/%m/%y %Hh%M CET')
        s = 's' if self.channel_count > 1 else ''
        duration = round(self.duration * 10) / 10
        return "{0} | {1.channel_count} voie{2} | {1.sample_rate} Hz | {3} s".format(dt, self, s, duration)


class LDSFChannel(object):
    """Métadonnées par voie, méthodes pour lire les données"""
    
    def __init__(self, ldsf_reader, index, name):
        self.__reader = ldsf_reader
        self._index = index
        self._name = name
        self._first_sample_time = 0.0
        self._sample_rate = 1.0
        self._unit = '/'
        self._weighting = 'None'
        self._description = ''
        self._samples_count = 0
        self._input_id = ''
        self.comment = ''
        self.dB_reference = 1
        self.type = ''
        self.group = 'Other'
        #self.color = None

    @property
    def key(self):
        """Clé : combinaison de index et name
        (l'index ne suffit pas pour raw tacho par ex.)"""
        return ':'.join((str(self._index), self._name))

    @property
    def name(self):
        """Nom de la voie de mesure"""
        return self._name

    @property
    def channel_index(self):
        return self._index

    @property
    def unit(self):
        """Unité de mesure de la voie"""
        return self._unit

    @property
    def weighting(self):
        return self._weighting

    @property
    def description(self):
        """Description de la voie de mesure"""
        return self._description

    @property
    def input_id(self):
        """Nom de la voie physique de mesure"""
        return self._input_id

    @property
    def number_of_samples(self):
        return self._samples_count

    @property
    def sample_rate(self):
        return self._sample_rate

    def __str__(self):
        if self.type:
            string = '[{0._index}] {0.name} ({0.type} in {0.unit})'.format(self)
        else:
            string = '[{0._index}] {0.name} ({0.unit})'.format(self)
        if self.input_id:
             string += ' on {0.input_id}'.format(self)
        return string

    def scaled(self, position=0, count=None):
        """Chargement du signal à plein échantillonnage en Pandas Series"""
        import pandas
        if count is None:
            count = self._samples_count
        data, time = self.__reader.get_samples(self.key, position, count)
        if time.size:
            return pandas.Series(data=data, index=time, name=self.name)
        else:
            return pandas.Series({}, name=self.name)

    def reduced(self):
        """Chargement du signal réduit (min et max à échelle réduite) en Pandas DataFrame"""
        import pandas
        data, time = self.__reader.get_reduced(self.key)
        if time.size:
            return pandas.DataFrame(data=data, index=time, columns=['min', 'max'])
        else:
            return pandas.DataFrame({}, columns=['min', 'max'])

    def series(self):
        """Pandas Series pour plot()"""
        data = self.scaled()
        return data

    def series_generator(self, chunk_size):
        """Generator yielding channel data as chunks of pandas series

        :param chunk_size: length of chunked series
        :type chunk_size: int
        :returns: pandas.Series
        """
        import pandas
        count = self._samples_count
        for chunk in range(0, count, chunk_size):
            chunk_size = min(chunk_size, count - chunk)
            data, time = self.__reader.get_samples(self.key, chunk, chunk_size)
            yield pandas.Series(data=data, index=time)

    def plot(self, *args, **kwargs):
        """Affichage d'une série avec matplotlib"""
        ax = self.series().plot(*args, **kwargs)
        ax.set_ylabel(self.unit)
        return ax


# script = """
# b = b'\x12\x03\x01\x01'
# # n = struct.unpack('<i', b)[0]
# n = int.from_bytes(b, byteorder='little', signed=False)"""
# timeit.timeit(setup = 'import struct', stmt = script)
class LDSFBinaryReader(object):
    """Binary reader pour LDSF"""

    def __init__(self, stream):
        self.stream = stream
        self._version = ''
        self._start_store_time = None
        self._channels = dict()
        self._channel_keys = dict()

        self.LABEL_DICT = { # type=None -> sous-bloc de métadonnées
            3: ('Creation time', self.read_posix),
            4: ('Creation time 2', self.read_posix),
            5: ('Last modification time', self.read_posix),
            6: ('Last modification time 2', self.read_posix),
            7: ('Editor', self.read_char),
            8: ('Data source', self.read_char),
            13: ('User channel id', self.read_char),
            14: ('Input id', self.read_char),  # Voie physique
            15: ('Unique index', self.read_uint), # Index absolu des données brutes
            16: ('Physical unit', None),
            17: ('Samples count', self.read_uint),
            18: ('Actual sensitivity', self.read_varnum),
            19: ('Sensitivity unit', None),
            20: ('Weighting', self.read_int),
            21: ('Label 21', self.read_uint),
            23: ('Speed ramp', self.read_char),
            24: ('Label 24', self.read_int),
            25: ('X axis first sample', self.read_fraction),
            26: ('X axis increment', self.read_fraction),
            27: ('Integer correction factor', self.read_float),
            28: ('Zero compensation', self.read_varnum),
            37: ('Group index', self.read_uint), # Absolu
            38: ('Local index', self.read_uint), # Relatif au groupe
            39: ('Data offsets', self.read_uint64),
            40: ('Data type', self.read_int),
            41: ('Name', self.read_char),
            43: ('MKS_m', self.read_int),
            44: ('MKS_kg', self.read_int),
            45: ('MKS_s', self.read_uint),
            46: ('MKS_A', self.read_int),
            47: ('MKS_K', self.read_int),
            50: ('MKS_rad', self.read_int),
            51: ('Gain', self.read_varnum),
            52: ('Offset', self.read_varnum),
            53: ('dB reference', self.read_float),
            54: ('Unit', self.read_char),
            55: ('Min value', self.read_varnum),
            56: ('Max value', self.read_varnum),
            57: ('Label 57', self.read_int),
            58: ('Comment', self.read_char),
            59: ('DOF id', self.read_char),
            61: ('Channel group', self.read_int),
            62: ('Unique index link', self.read_int), # Référence à un 'Unique index' (Label 15)
            67: ('Formula', self.read_char),
            70: ('Label 70', self.read_uint),
            71: ('Label 71', self.read_uint),
            72: ('Label 72', self.read_char),
            74: ('Channel index', self.read_uint), # (pas unique si tacho raw) Numéro de voie LMS
            77: ('Unique index link 2', self.read_uint), # Référence à un 'Unique index' (Label 15)
            78: ('Scale ratio', self.read_uint), # Pour données min-max
            79: ('Scale power', self.read_uint), # Nombre d'applications de 'Scale ratio', pour données min max
            80: ('Next header position', self.read_uint),
            81: ('Size of next header', self.read_int),
            83: ('Signal groups', None),
            84: ('Signals', None),
            85: ('MinMax groups', None),
            86: ('MinMax', None),
            87: ('Annotations group', None),
            88: ('Annotations', None),
            89: ('Block length', self.read_uint), # En nombre d'échantillons
            90: ('Data format', None),
            91: ('Index of data offset', self.read_uint),
            92: ('Byte length with free space', self.read_uint),
            93: ('Data types', self.read_uint8),
            94: ('Source data folder', self.read_char),
            95: ('Source data name', self.read_char),
            96: ('Absolute time', self.read_lmsdate),
            97: ('Clock source', self.read_char),
            102: ('Absolute time status', self.read_char),
            107: ('Label 107', self.read_int),
            108: ('Physical unit 2', None),
            109: ('Label 109', self.read_int),
            110: ('Physical unit 3', None),
            111: ('Short channel id', self.read_char),
            112: ('Group', self.read_char),
            130: ('Range max', self.read_varnum),
            131: ('Range min', self.read_varnum),
            132: ('Physical unit 4', None),
            139: ('Label 139', self.read_uint),
            140: ('Unit format', None),
            141: ('Label 141', self.read_uint),
            142: ('Label compatible units', None),
            147: ('Label 147', self.read_uint), # Offset pour physical unit 2 ?
            148: ('Compatible units', None),
            149: ('Label 149', self.read_uint),
            150: ('Raw physical unit', None),
            151: ('Label 151', self.read_uint),
            152: ('Label 152', self.read_uint),
            159: ('Label 159', self.read_uint), # 0, sinon 4 pour GPS
            160: ('ID voie', self.read_uint),
            161: ('ID module', self.read_uint), # 1000 pour GPS
            163: ('ID module serial', self.read_char),
            165: ('Label 165', self.read_uint),
            166: ('Raw physical unit 2', None)}
        self.INDEXED_IDS = (83, 84, 85, 86, 87, 88, 148)
        #self.USEFUL_IDS = (3, 13, 14, 16, 17, 25, 26, 27, 28, 38, 39, 40, 41, 51, 52, 53, 54, 58, 59, 80, 83, 84, 89, 90, 93, 96)

        # Lecture des métadonnées de stream
        self.metadata = self._read_header()

    def close(self):
        self.stream.close()

#    def unpack(self, fmt, nbytes=1):
#        value = struct.unpack(fmt, self.stream.read(nbytes))
#        if len(value) == 1:
#            return value[0]
#        else:
#            return value

    def unpack(self, fmt, nbytes=1):
        value = numpy.fromfile(self.stream, 'B', nbytes)
        value = value.view(fmt).tolist()
        if len(value) == 1:
            return value[0]
        else:
            return value
    
    # def read_byte(self, nbytes=1):
    #     #try:
    #     return self.stream.read(nbytes)
    #     #except Exception as e:
    #     #    raise LDSFStatus(4) # "file corrupt"

    # def read_bool(self):
    #     return bool.from_bytes(self.stream.read(1), byteorder='little', signed=False)
    #     # return self.unpack('?')

    def read_uint8(self, nbytes=1):
        """Retourne un tuple() d'entiers 8 bits, de taille `nbytes`"""
        #return self.unpack('<' + 'B'*nbytes, nbytes)
        if nbytes==1:
            return (self.unpack('B', nbytes), )
        else:
            return tuple(self.unpack('B', nbytes))

    # def read_int16(self, nbytes=2):
    #     return self.unpack('<' + 'h'*(nbytes//2), nbytes)
    
    def read_int16(self, nbytes=2):
        """Lecture d'entiers signés 16 bits en numpy.array()"""
        if nbytes % 2 == 0:
            return numpy.fromfile(self.stream, dtype='<h', count=nbytes//2)
        else:
            self.stream.seek(nbytes, 1)
            return None
            
    # def read_uint16(self, nbytes=2):
    #     return self.unpack('<' + 'H'*(nbytes//2), nbytes)

    def read_int24(self, nbytes=3):
        """Lecture d'entiers signés 24 bits en numpy.array()"""
        if nbytes % 3 == 0:
            a3 = numpy.fromfile(self.stream, dtype='B', count=nbytes)
            a4 = numpy.empty((nbytes//3, 4), dtype='B')
            a4[..., :3] = a3.reshape((-1, 3))
            a4[..., 3] = (a4[..., 2] >> 7) * 255
            return a4.view('<i').reshape(a4.shape[:-1])
        else:
            self.stream.seek(nbytes, 1)
            return None

    # def read_int32(self, nbytes=4):
    #     return self.unpack('<' + 'i'*(nbytes//4), nbytes)

    # def read_uint32(self, nbytes=4):
    #     return self.unpack('<' + 'I'*(nbytes//4), nbytes)

    # def read_int64(self, nbytes=8):
    #     return self.unpack('<' + 'q'*(nbytes//8), nbytes)

    def read_uint64(self, nbytes=8):
        """Retourne un tuple() d'entiers 64 bits, de taille `nbytes/8`"""
        if nbytes % 8 == 0:
            #return self.unpack('<' + 'Q'*(nbytes//8), nbytes)
            if nbytes == 8:
                return (self.unpack('<Q', nbytes), )
            else:
                return tuple(self.unpack('<Q', nbytes))
        else:
            self.stream.seek(nbytes, 1)
            return None

    def read_single(self, nbytes=4):
        """Lecture de réels simples 32 bits en numpy.array()"""
        if nbytes % 4 == 0:
            return numpy.fromfile(self.stream, dtype='<f', count=nbytes//4)
        else:
            self.stream.seek(nbytes, 1)
            return None

    # def read_single(self, nbytes=4):
    #     """Retourne un tuple de réels simples, de taille `nbytes/4`"""
    #     if nbytes % 4 == 0:
    #         return self.unpack('<' + 'f'*(nbytes//4), nbytes)
    #     else:
    #         self.stream.seek(nbytes, 1)
    #         return None

    def read_double(self, nbytes=8):
        """Lecture de réels doubles 64 bits en numpy.array()"""
        if nbytes % 8 == 0:
            return numpy.fromfile(self.stream, dtype='<d', count=nbytes//8)
        else:
            self.stream.seek(nbytes, 1)
            return None
            
    # def read_double(self, nbytes=8):
    #     """Retourne un tuple de réels doubles, de taille `nbytes/8`"""
    #     if nbytes % 8 == 0:
    #         return self.unpack('<' + 'd'*(nbytes//8), nbytes)
    #     else:
    #         self.stream.seek(nbytes, 1)
    #         return None

    def read_varint(self):
        """Lecture d'1 entier de longueur variable"""
        value = self.read_uint(1)
        if value == 253:
            return self.read_uint(2)
        elif value == 254:
            return self.read_uint(4)
        elif value == 255:
            return self.read_uint(8)
        return value

    def read_varnum(self, nbytes):
        """Lecture d'un int ou d'un réel double en fonction de `nbytes`"""
        if nbytes in (1, 2, 4):
            return int.from_bytes(self.stream.read(nbytes), byteorder='little', signed=True)
        elif nbytes == 8:
            return self.read_float(8)
        else:
            self.stream.seek(nbytes, 1)
            return None

    def read_int(self, nbytes):
        """Retourne 1 entier signé codé sur `nbytes` octets"""
        if nbytes in (1, 2, 4, 8):
            return int.from_bytes(self.stream.read(nbytes), byteorder='little', signed=True)
        else:
            self.stream.seek(nbytes, 1)
            return None

    def read_uint(self, nbytes):
        """Retourne 1 entier non signé codé sur `nbytes` octets"""
        if nbytes in (1, 2, 4, 8):
            return int.from_bytes(self.stream.read(nbytes), byteorder='little', signed=False)
        else:
            self.stream.seek(nbytes, 1)
            return None

    def read_float(self, nbytes):
        """Retourne 1 réel simple ou double codé sur `nbytes` octets"""
        if nbytes == 4:
            return self.unpack('<f', nbytes)
        elif nbytes == 8:
            return self.unpack('<d', nbytes)
        else:
            self.stream.seek(nbytes, 1)
            return None

    def read_posix(self, nbytes):
        """Retourne une date `datatime`"""
        import pytz
        if nbytes == 4:
            from datetime import datetime
            return datetime.utcfromtimestamp(self.read_int(4)).replace(tzinfo=pytz.utc)
        else:
            self.stream.seek(nbytes, 1)
            return None

    def read_lmsdate(self, nbytes):
        """Retourne une date `datatime` à partir d'une date LMS
        au format `2018-08-31 12:16:45 ms 267.740000`"""
        # if nbytes == 20:
        #     lmsdate = self.stream.read(nbytes-1).decode(encoding=encoding)
        #     self.stream.seek(1, 1)
        #     return datetime.strptime(lmsdate, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.utc)
        if nbytes == 34:
            import pytz
            from datetime import datetime
            lmsdate = self.stream.read(nbytes-1).decode(encoding=encoding)
            self.stream.seek(1, 1)
            lmsdate = lmsdate[:20] + lmsdate[23:26] + lmsdate[27:30] # + '.' + lmsdate[30:]
            return datetime.strptime(lmsdate, '%Y-%m-%d %H:%M:%S %f').replace(tzinfo=pytz.utc)
        else:
            print('read_lmsdate : format non reconnu.')
            self.stream.seek(nbytes, 1)
            return None

    def read_fraction(self, nbytes):
        """Retourne une durée en secondes sous forme de fraction"""
        from fractions import Fraction
        b1 = self.read_uint(1)
        num = int.from_bytes(self.stream.read(b1), byteorder='little', signed=True)
        b2 = self.read_uint(1)
        den = int.from_bytes(self.stream.read(b2), byteorder='little', signed=True)
        if nbytes == (b1+b2+2):
            value = Fraction(num, den)
            return value
            # return float(value)
        else:
            raise LDSFStatus(4) # "file corrupt"

    def read_char(self, nbytes):
        """Retourne une chaîne de caractères (le byte 0x00 de fin est ignoré)"""
        c = self.stream.read(nbytes-1).decode(encoding=encoding)
        self.stream.seek(1, 1)
        return c

    def ceil_int(self, a, step):
        """Arrondi de `a` au step supérieur pour `a` et `step` entiers"""
        if isinstance(a, int) and isinstance(step, int):
            return a + (-a) % step
            # return -step * (-a // step)
        else:
            raise TypeError

    def get_weighting(self, w_id):
        """L20 'Weighting'"""
        temp_dict = {0: 'None', 1:'A', 2:'B', 3:'C', 4:'D'}
        return temp_dict.get(w_id, 'Unknown')

    def get_data_type(self, type_id):
        """L40 'Data type'"""
        temp_dict = {0:('', 0), 3:('int16', 2), 4:('int24', 3), 7:('single', 4), 8:('double', 8)}
                   # 2:('int8', 1), 5:('int32', 4) 9:? # TODO à valider
        return temp_dict[type_id] # .get(type_id, (None, None))

    def get_channel_group(self, group_id):
        """L61 'Channel group'"""
        temp_dict = {0: 'Vibration', 1:'Acoustic', 2:'Other', 3:'Static', 4:'Tacho', 7:'Octave', 8:'Control', 9:'Measure', 10:'Status'}
        return temp_dict.get(group_id, 'Other')

    def deep_update(self, a, b, path=None):
        "a.update(b) pour des dictionnaires imbriqués"
        if path is None:
            path = []
        for key in b:
            if key in a:
                if isinstance(a[key], dict) and isinstance(b[key], dict):
                    self.deep_update(a[key], b[key], path + [str(key)])
                elif a[key] == b[key]:
                    pass
                else:
                    a[key] = b[key]
                    print('Remplacé : ' + '.'.join(path + [str(key)]))
            else:
                a[key] = b[key]
        return a

    def _getblock(self, block_label_id=None):
        """
        Décodage d'un 'block' de métadonnées
        Retourne:
        (dictionnaire des métadonnées, index du block) pour les blocks indéxés
          ou
        (dictionnaire des métadonnées, next_header_pos) pour les blocks de niveau 0
        """
        byte_size = self.read_varint() # Taille du block
        max_pos = self.stream.tell() + byte_size
        block = dict()
        block_index = None
        while self.stream.tell() < max_pos:
            label_id = self.read_uint(1) # Lecture du label ID (1 byte)
            # if label_id == 0:
            #     raise LDSFStatus(4) # "file corrupt"
            label_name, label_reader = self.LABEL_DICT.get(label_id, ('Unknown label id ' + str(label_id), self.read_uint8))
            if label_reader is None: # Nouveau sous-bloc
                # print('+L' + str(label_id))
                sub_block, idx = self._getblock(label_id)
                if idx is not None:
                    block[label_name] = self.deep_update(block.get(label_name, dict()), {idx: sub_block})
                else:
                    block[label_name] = self.deep_update(block.get(label_name, dict()), sub_block)
            else:
                byte_size = self.read_varint()
                if label_id in (81, ): # Labels à ignorer
                     self.stream.seek(byte_size, 1)
                     continue
                # if label_id not in self.USEFUL_IDS:
                #      self.stream.seek(byte_size, 1)
                #      continue
                # Lecture d'une métadonnée
                value = label_reader(byte_size)
                #print(' L' + str(label_id), value)
                if (label_id == 3 and self._start_store_time is None) or (label_id == 96):
                    self._start_store_time = value
                if label_id == 80:
                    next_header_pos = value
                elif block_index is None and block_label_id in self.INDEXED_IDS:
                    block_index = value
                else:
                    # if label_name[:7] == 'Unknown':
                    #     print(label_name, value)
                    block[label_name] = value
        
        return (block, block_index) if block_label_id else (block, next_header_pos)

    def _read_header(self):
        """
        Lecture des métadonnées du fichier complet
        Retourne un dictionnaire
        """
        # Lecture de l'identifiant fichier en position 0
        self.stream.seek(0, 0)
        self._version = self.stream.read(64).rstrip(b'\x00').decode(encoding='ascii')
        if not self._version[:25] == 'LMS Data Streaming Format':
            raise LDSFStatus(1) # "not a LDSF file"
        # Lecture de toutes les métadonnées
        metadata = dict()
        next_header_pos = self.stream.tell() # Position de l'en-tête du header
        while next_header_pos > 0:
            self.stream.seek(next_header_pos, 0)
            header_id = int.from_bytes(self.stream.read(8), byteorder='little', signed=True)
            if header_id != -1:
                raise LDSFStatus(4) # "file corrupt"
            # Lecture des métadonnées de l'en-tête
            block, next_header_pos = self._getblock()
            self.deep_update(metadata, block) # Fusion des métadonnées
        return metadata

    def get_channel_list(self):
        """
        Retourne une classe `LDSFFileInfo` pour les infos globales du fichier
        et une classe `LDSFChannel` par voie en `tuple`
        """
        channels = []
        sample_rate = 0
        duration = 0
        for signal_group in self.metadata['Signal groups'].values():
            for i, signal in signal_group['Signals'].items():
                if i == 0: # Axe des abscisses (toujours en premier)
                    # Axe équidistant:
                    first_sample = signal['Data format'].get('X axis first sample', 0)
                    delta_t = signal['Data format'].get('X axis increment', 1)
                    sample_rate = max(sample_rate, 1/delta_t)
                    # unit_info = signal.get('Physical unit', None)
                    # if unit_info is not None:
                    #     x_unit = unit_info.get('Unit', '/')
                    # TODO gérer axe non équidistant
                    continue
                # Voies de mesures
                samples_count = signal['Samples count']
                if samples_count == 0:
                    continue # On ne conserve pas les voies vides
                if signal['Physical unit']['Unit'] == 's': # Raw:tacho
                    duration = max(duration, float(signal['Max value']))
                else:
                    duration = max(duration, float((samples_count-1)*delta_t))
                # Création d'1 nouvelle voie de mesure indexée par index et name
                index = signal['Channel index'] # numéro de voie LMS
                # index = signal.get('Channel index', None)  # numéro de voie LMS
                # if index is None:
                #     print('------------OUPS')
                #     raise LDSFStatus(4) # "file corrupt" 
                name = signal.get('DOF id', None)
                if name is None:
                    name = signal.get('User channel id', '')
                    if not name:
                        name = signal.get('Input id', '')
                        if not name:
                            name = 'C' + index
                channel = LDSFChannel(self, index, name) # Métadonnées de la voie en cours (retournée)
                self_channel = dict() # Infos de lecture de la voie en cours (dans self)
                channel._first_sample_time = first_sample
                channel._sample_rate = 1/delta_t
                channel._samples_count = samples_count
                channel._input_id = signal.get('Input id', '')
                channel._description = signal.get('User channel id', '')
                data_format = signal.get('Data format', None)
                if data_format is None:
                    data_type, type_bytes = (None, None) # Si `None`, lu dans le mini-header
                    gain, offset = 1, 0
                else:
                    data_type, type_bytes = self.get_data_type(data_format['Data type'])
                    gain = data_format.get('Integer correction factor', 1)
                    offset = data_format.get('Zero compensation', 0)
                unit_info = signal.get('Physical unit', None)
                if unit_info is None:
                    unit_gain, unit_offset = 1, 0
                else:
                    channel._unit = unit_info.get('Unit', '/')
                    unit_gain = unit_info.get('Gain', 1)
                    unit_offset = unit_info.get('Offset', 0)
                    channel.type = unit_info.get('Name', '')
                    channel.dB_reference = unit_info.get('dB_reference', 1)
                channel._weighting = self.get_weighting(signal.get('Weighting', 0))
                channel.group = self.get_channel_group(signal.get('Channel group', None))
                channel.comment = signal.get('Comment', '')
                self_channel['samples_count'] = samples_count
                self_channel['delta_t'] = delta_t
                self_channel['first_sample'] = first_sample
                self_channel['data_type'] = data_type
                self_channel['type_bytes'] = type_bytes
                self_channel['gain'] = gain * unit_gain
                self_channel['offset'] = unit_offset + offset * unit_gain
                # Stockage des données de la voie :
                self._channels[channel.key] = self_channel # Infos de lecture de la voie en cours (dans self)
                self._channel_keys[signal['Unique index']] = channel.key # Unique index -> key
                channels.append(channel) # Métadonnées de la voie en cours (retournée)
        
        # Compilation des informations de localisation des données brutes complètes
        for signal_group in self.metadata['Signal groups'].values():
            # block_length = signal_group.get('Block length', None)
            block_length = signal_group['Block length']
            # Si l'axe x est équidistant :
            #channel_links = [(i, ':'.join((str(v['Channel index']), v['DOF id']))) for i, v in signal_group['Signals'].items() if i]
            # Sinon, TODO gérer l'axe non équidistant :
            channel_links = [(i, v.get('Channel index', None), v.get('DOF id', None)) for i, v in signal_group['Signals'].items()]
            channel_links = [(a[0], ':'.join((str(a[1]), a[2]))) for a in channel_links if a[1] is not None]
            channel_links.sort()
            #channel_links = sorted(channel_links)
            n = channel_links[-1][0] # Dernier index de channel
            block_positions = tuple([[] for x in range(n+1)]) # Positions de démarrage des données
            block_samples_cumsum = tuple([[0] for x in range(n+1)]) # Nombre d'échantillons cumulés, à la fin du block en cours
            cumsum = [0]*(n+1)
            for pos in signal_group['Data offsets']:
                for i, key in channel_links:
                    block_positions[i].append(pos)
                    a = block_length * self._channels[key]['type_bytes']
                    pos += self.ceil_int(a, 4)
                    cumsum[i] += block_length
                    block_samples_cumsum[i].append(cumsum[i])
            for i, key in channel_links:
                self._channels[key].update({'block_positions': tuple(block_positions[i]),
                                       'block_samples_cumsum': tuple(block_samples_cumsum[i][:-1])})

        # Compilation des informations de localisation des données brutes réduites
        for minmax_group in self.metadata['MinMax groups'].values():
            scale_power = minmax_group['Scale power']
            if scale_power != 1:
                continue
            scale_ratio = minmax_group['Scale ratio']
            reduced_samples_count = minmax_group['MinMax'][0]['Samples count']
            block_length = minmax_group['Block length']
            unique_index = minmax_group['Unique index link 2']
            key = self._channel_keys[unique_index]
            min_block_positions = [] # Positions de démarrage des données min
            max_block_positions = [] # Positions de démarrage des données max
            block_samples_cumsum = [0] # Nombre d'échantillons cumulés, à la fin du block en cours
            cumsum = 0
            for pos in minmax_group['Data offsets']:
                min_block_positions.append(pos)
                a = block_length * self._channels[key]['type_bytes']
                pos += self.ceil_int(a, 4)
                max_block_positions.append(pos) # 28640
                cumsum += block_length
                block_samples_cumsum.append(cumsum)
            self._channels[key].update({'min_block_positions': tuple(min_block_positions),
                                        'max_block_positions': tuple(max_block_positions),
                                        'scale_ratio': scale_ratio,
                                        'reduced_samples_count': reduced_samples_count,
                                        'reduced_block_samples_cumsum': tuple(block_samples_cumsum[:-1])})

        channels.sort(key=lambda x: x._index) # x.key possible mais peut inverser les raw:tacho
        return (LDSFFileInfo(sample_rate, self._start_store_time, duration, len(channels), self._version), tuple(channels))

    def _read_rawdata(self, pos, cnt, data_type, read_so_far, data):
        """Lecture des données brutes d'une voie en numpy.array()"""
        self.stream.seek(pos, 0)
        if data_type == 'int24':
            data[read_so_far:(read_so_far+cnt)] = self.read_int24(cnt*3)
        elif data_type == 'single':
            data[read_so_far:(read_so_far+cnt)] = self.read_single(cnt*4)
        elif data_type == 'double':
            data[read_so_far:(read_so_far+cnt)] = self.read_double(cnt*8)
        elif data_type == 'int16':
            data[read_so_far:(read_so_far+cnt)] = self.read_int16(cnt*2)
        read_so_far += cnt
        return read_so_far

    def get_samples(self, key, position=None, count=None):
        """
        Lecture des échantillons de la voie `key`
        depuis l'échantillon `position`
        pour un total de `count` échantillons
        Retourne 2 numpy.array(dtype=float)
        `(data, time)`
        """
        samples_count = self._channels[key]['samples_count']
        if position is None:
            position = 0
        if position < 0:
            return numpy.empty(0), numpy.empty(0)
        if count is None:
            count = samples_count
        if count <= 0:
            return numpy.empty(0), numpy.empty(0)
        count = min(position+count, samples_count)-position
        # Dimensionnement des sorties
        data = numpy.empty(count, dtype=float)
        # TODO gérer axe non équidistant
        #time = numpy.empty_like(data) 
        # time = numpy.arange(position, count, dtype=float) * self._channels[key]['delta_t'].numerator / self._channels[key]['delta_t'].denominator
        time = numpy.arange(position, position+count, dtype=float) * float(self._channels[key]['delta_t']) + float(self._channels[key]['first_sample'])
        # Taille d'un échantillon de données en octets
        data_type = self._channels[key]['data_type']
        type_bytes = self._channels[key]['type_bytes']
        # Recherche des blocks concernés par la lecture des données
        block_positions = numpy.asarray(self._channels[key]['block_positions'])
        block_samples_cumsum = numpy.asarray(self._channels[key]['block_samples_cumsum'])
        first_data_block = numpy.searchsorted(block_samples_cumsum, position, 'right') - 1
        last_data_block = numpy.searchsorted(block_samples_cumsum, position+count, 'right') - 1
        read_so_far = 0
        # Lecture dans le premier block
        pos = block_positions[first_data_block] + type_bytes*(position - block_samples_cumsum[first_data_block])
        cnt = count if (last_data_block == first_data_block) else (block_samples_cumsum[first_data_block+1] - position)
        read_so_far = self._read_rawdata(pos, cnt, data_type, read_so_far, data)
        # Lecture des blocks suivants
        for b in range(first_data_block + 1, last_data_block):
            pos = block_positions[b]
            cnt = block_samples_cumsum[b+1] - block_samples_cumsum[b]
            read_so_far = self._read_rawdata(pos, cnt, data_type, read_so_far, data)
        # Lecture dans le dernier block
        if last_data_block != first_data_block:
            pos = block_positions[last_data_block]
            cnt = position + count - block_samples_cumsum[last_data_block]
            read_so_far = self._read_rawdata(pos, cnt, data_type, read_so_far, data)
        # Mise à l'échelle
        gain = self._channels[key]['gain']
        offset = self._channels[key]['offset']
        if gain != 1:
            data *= gain
        if offset != 0:
            data += offset

        return data, time

    def get_reduced(self, key, position=None, count=None):
        """
        Lecture des échantillons réduits (min et max)
        de la voie `key` depuis l'échantillon `position`
        pour un total de `count` échantillons
        Retourne 2 numpy.array(dtype=float)
        `(data, time)`
        """
        scale_ratio = self._channels[key].get('scale_ratio', None)
        if scale_ratio is None:
            return numpy.empty(0), numpy.empty(0)
        # samples_count = self._channels[key]['samples_count'] // scale_ratio
        samples_count = self._channels[key]['reduced_samples_count']
        if position is None:
            position = 0
        if position < 0:
            return numpy.empty(0), numpy.empty(0)
        if count is None:
            count = samples_count
        if count <= 0:
            return numpy.empty(0), numpy.empty(0)
        count = min(position+count, samples_count)-position
        # Dimensionnement des sorties
        min_data = numpy.empty(count, dtype=float)
        max_data = numpy.empty(count, dtype=float)
        time = numpy.arange(position, count, dtype=float) * scale_ratio * float(self._channels[key]['delta_t']) + float(self._channels[key]['first_sample'])
        # Taille d'un échantillon de données en octets
        data_type = self._channels[key]['data_type']
        type_bytes = self._channels[key]['type_bytes']
        # Recherche des blocks concernés par la lecture des données
        min_block_positions = numpy.asarray(self._channels[key]['min_block_positions'])
        max_block_positions = numpy.asarray(self._channels[key]['max_block_positions'])
        reduced_block_samples_cumsum = numpy.asarray(self._channels[key]['reduced_block_samples_cumsum'])
        first_data_block = numpy.searchsorted(reduced_block_samples_cumsum, position, 'right') - 1
        last_data_block = numpy.searchsorted(reduced_block_samples_cumsum, position+count, 'right') - 1
        read_so_far = 0
        # Lecture dans le premier block
        min_pos = min_block_positions[first_data_block] + type_bytes*(position - reduced_block_samples_cumsum[first_data_block])
        max_pos = max_block_positions[first_data_block] + type_bytes*(position - reduced_block_samples_cumsum[first_data_block])
        cnt = count if (last_data_block == first_data_block) else (reduced_block_samples_cumsum[first_data_block+1] - position)
        self._read_rawdata(min_pos, cnt, data_type, read_so_far, min_data)
        read_so_far = self._read_rawdata(max_pos, cnt, data_type, read_so_far, max_data)
        # Lecture des blocks suivants
        for b in range(first_data_block + 1, last_data_block):
            min_pos = min_block_positions[b]
            max_pos = max_block_positions[b]
            cnt = reduced_block_samples_cumsum[b+1] - reduced_block_samples_cumsum[b]
            self._read_rawdata(min_pos, cnt, data_type, read_so_far, min_data)
            read_so_far = self._read_rawdata(max_pos, cnt, data_type, read_so_far, max_data)
        # Lecture dans le dernier block
        if last_data_block != first_data_block:
            min_pos = min_block_positions[last_data_block]
            max_pos = max_block_positions[last_data_block]
            cnt = position + count - reduced_block_samples_cumsum[last_data_block]
            self._read_rawdata(min_pos, cnt, data_type, read_so_far, min_data)
            read_so_far = self._read_rawdata(max_pos, cnt, data_type, read_so_far, max_data)
        # Mise à l'échelle
        data = numpy.vstack((min_data, max_data)).T
        gain = self._channels[key]['gain']
        offset = self._channels[key]['offset']
        if gain != 1:
            data *= gain
        if offset != 0:
            data += offset

        return data, time


class LDSFFile(collections.abc.Mapping):
    """Classe du fichier ldsf, qui 'mappe' les noms de voies et leurs métadonnées"""

    def __init__(self, source=None):
        self.name = ''       # Nom du fichier ouvert
        self.closed = True   # Etat du fichier ouvert ou fermé
        self.__reader = None # Objet reader de file
        # self.__fid = None

        if source:
            self.open(source) # En cas d'erreur, l'instance de LDSFFile n'est pas construite

    def activate(self):
        """Vérification de l'état du fichier"""
        if self.closed:
            raise ValueError('I/O operation on closed file.')
        
    def open(self, source):
        """Ouvre le fichier `source` et charge les métadonnées"""
        self.close() # Vérification que le fichier n'était pas déjà ouvert
        try:
            if hasattr(source, 'read'): # La source est un objet file-like
                self.__reader = LDSFBinaryReader(source)
            else:   # On suppose qu'il s'agit d'un nom de fichier (en str)
                if not source.lower().endswith('.ldsf'):
                    source += '.ldsf'
                self.__reader = LDSFBinaryReader(io.open(source, 'rb', buffering=2**20))
            self.name = self.__reader.stream.name
            self.closed = False
            # Lecture des métadonnées du fichier et des voies
            self.info, self.channels = self.__reader.get_channel_list()
        except:
            self.close()
            raise

    @property
    def header(self):
        """Retourne toutes les métadonnées du fichier"""
        self.activate()
        # import json
        # return json.dumps(self.__reader.metadata)
        return self.__reader.metadata

    def dataframe(self, channels=None):
        """Retourne un dataframe avec les séries sélectionnées"""
        import pandas
        self.activate()
        if not channels:
            # Par défaut, toutes les voies
            channels = self.keys()
        return pandas.DataFrame({self[k].key: self[k].series() for k in channels})

    def close(self):
        """Ferme le fichier ldsf"""
        if not self.closed:
            self.activate()
            self.__reader.close()
            self.closed = True
            self.channels = []

    def __len__(self):
        return len(self.channels)

    def __getitem__(self, key):
        self.activate()
        if isinstance(key, int):
            for ch in self.channels:
                if ch._index == key:
                    return ch
        else:
            for ch in self.channels:
                if ch.key == key or ch._name == key or ch._input_id == key:
                    return ch
        raise KeyError(key)

    def __iter__(self):
        for ch in self.channels:
            yield ch.key

    def __str__(self):
        return self.name

    def __enter__(self):
        """Maintien le fichier dans le contexte (with ... :)"""
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        """Ferme le fichier lorsqu'il sort du contexte"""
        self.close()


# Méthodes de module
def open(source):
    return LDSFFile(source)

if __name__ == '__main__':
    import locale
    # locale.setlocale(locale.LC_TIME, 'french_France')
    ldsf = open('C:/TEMP/test.ldsf')
    # ldsf = open('test.ldsf')
    # ldsf = open('C:/Passerelles/LDSF/MixedFS.ldsf')
    # ldsf = open(r'C:\Program Files (x86)\LMS\LMS Test.Lab 17\Tecware\demo\general\LPG1 - undulating road.ldsf')
    print(ldsf.info)
    print(list(ldsf.keys()))
    for ch in ldsf.channels:
        print(ch)
    print(ldsf[3].reduced().head())
    ax = ldsf[3].plot()
