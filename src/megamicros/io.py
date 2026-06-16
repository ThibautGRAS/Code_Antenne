#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import glob
import time
import configparser
from collections import OrderedDict
from datetime import datetime
import os.path as osp
import numpy as np
import warnings


class MegamicrosIOWarning(Warning):
    """A class to manage Megamicros input/output warnings"""
    pass


# ===========================
# DAT FILE
# ===========================

class DatFile():
    def __init__(self, path, mode="r"):
        self.filename = path
        self.__file = None
        self.__mode = mode
    
    def open(self, **kwargs):
        self.__file = open(self.filename, mode=self.__mode + "b")

    def write(self, data):
        self.__file.write(data)
    
    def close(self):
        self.__file.close()
    
    def dump_log(self, parameters, options=None, message=""):
        config = configparser.ConfigParser()
        if options is None:
            options = dict()
        config["Default"] = {
            "Time": time.ctime(),
        }
        config["Parameters"] = parameters
        config["Options"] = {
            "commentaire": message,
            **options,
        }
        output_name, _ = detect_extension(self.filename)
        with open(output_name + '.log', 'w') as configfile:
            config.write(configfile)


def read_dat(path, n_channels, n_analogs=0, counter=1, dtype='int32', **kwargs):
    """Open and read data from given `.dat` file.

    Parameters
    ----------
    path : str
        path to '.dat' file
    n_channels : int
        number of microphone channels used in recording
    n_analogs : int
        number of analog channels used in recording, by default 0
    counter : int, optional
        specify the use of the counter, by default 1 (see documentation)
    dtype : str, optional
        type of the data, by default 'int32'

    Returns
    -------
    n_samples
        total number of samples recorded
    data
        array of data, of size (n_samples x (n_channels + n_analogs + counter))
    """
    total_channels = counter + n_channels + n_analogs
    with open(path, "r") as file:
        data = np.fromfile(file, dtype=dtype)
        n_samples = len(data) // total_channels
        data = np.reshape(data, (n_samples, total_channels))
    return n_samples, data


def parse_log(path):
    """Parse parameters from a log file.

    Parameters
    ----------
    path : str
        path to log file

    Returns
    -------
    parameters
        dictionnary of parsed parameters
    options
        dictionnary of parsed optional parameters
    """
    config = configparser.ConfigParser()
    config.read(path)
    parameters = {}
    parameters["n_channels"] = config["Parameters"].getint("n_channels")
    parameters["n_analogs"] = config["Parameters"].getint("n_analogs")
    parameters["counter"] = config["Parameters"].getint("counter")
    parameters["samplingrate"] = config["Parameters"].getint("samplingrate")
    parameters["dtype"] = config["Parameters"].get("dtype")
    parameters["duration"] = config["Parameters"].getfloat("duration")
    options = {}
    for key in config["Options"]:
        options[key] = config["Options"].get(key)
    return parameters, options


def add_date_to_filename(filename):
    """Format a filepath to add the current date.

    Parameters
    ----------
    filename : str
        path to file

    Returns
    -------
    new_filename
        path to file with the current date
    """
    filename, ext = detect_extension(filename)
    date = datetime.now().strftime("%Y%m%d_%H%M%S")
    if filename is None:
        return "".join(["mesure_", date, ext])
    else:
        return "".join([filename, "_", date, ext])


def parse_filename(path, sep="_"):
    filename = osp.basename(path)
    name, _ = osp.splitext(filename)
    args = name.split(sep)
    return args[-2], args[-1], sep.join(args[:-2])


def detect_extension(path):
    """Detect the extension of the filename.

    Parameters
    ----------
    filename : str
        name of the file

    Returns
    -------
    name
        name without the extension
    ext
        the extension if it exists, else ".dat"
    """
    name, ext = osp.splitext(path)
    if ext == "": 
        return name, ".dat"
    else:
        return name, ext


def get_last_recording(dirpath):
    """Return the last recording file stored in 'dirpath'

    Parameters
    ----------
    dirpath : str
        path of the folder where is the last recording file.
    is_log : bool
        Return True if a log file is also stored inplace.
    """
    list_of_files = []
    for ext in __allowed_ext__.keys():
        path = osp.join(dirpath, "*%s" % ext)
        list_of_files += glob.glob(path)
    latest_file = max(list_of_files, key=osp.getctime)
    
    if ".dat" in latest_file and osp.exists(latest_file.replace(".dat", ".log")):
        return osp.basename(latest_file), True
    else:
        return osp.basename(latest_file), False


__allowed_ext__ = {
    ".dat": DatFile,
}


# ===========================
# HDF5 FILE
# ===========================

try:
    # IF H5PY IS INSTALLED
    import h5py

    class H5File(h5py.File):
        def open(self, size, dtype=np.int32):
            """Open an HDF5 output file.

            Parameters
            ----------
            size : int
                maximum amount of data to write in file
            dtype : [type], optional
                format of the input data, by default np.int32
            """
            self.data = self.create_dataset('/data', 
                shape=(0, ), maxshape=(size, ), dtype=dtype)
            self.__dtype = dtype
        
        def write(self, raw_data):
            """Write input data to HDF5 file.

            Parameters
            ----------
            input_data : int, array-like
                raw input data (in bytes) to write
            """
            input_data = np.frombuffer(raw_data, self.__dtype)
            actual_size = self.data.size
            input_size = len(input_data)
            self.data.resize((actual_size + input_size, ))
            self.data[-input_size:] = input_data
            self.flush()
        
        def dump_log(self, parameters, options=None, message=""):
            if options is None:
                options = dict()
            dset_parameters = self.create_group("/parameters")
            for key, item in parameters.items():
                if isinstance(item, str):
                    dset_parameters.create_dataset(key, data=item, dtype=h5py.string_dtype())
                else:
                    dset_parameters.create_dataset(key, data=item)
            dset_options = self.create_group("/options")
            dset_options.create_dataset("commentaire", data=message, dtype=h5py.string_dtype())
            for key, item in options.items():
                if isinstance(item, str):
                    dset_parameters.create_dataset(key, data=item, dtype=h5py.string_dtype())
                else:
                    dset_parameters.create_dataset(key, data=item)


    def read_h5(path, n_channels, n_analogs=0, counter=1, dtype='int32'):
        """Open and read data from given HDF5 file.

        Parameters
        ----------
        path : str
            path to HDF5 file
        n_channels : int
            number of microphone channels used in recording
        n_analogs : int
            number of analog channels used in recording, by default 0
        counter : int, optional
            specify the use of the counter, by default 1 (see documentation)
        dtype : str, optional
            type of the data, by default 'int32'

        Returns
        -------
        n_samples
            total number of samples recorded
        data
            array of data, of size (n_samples x (n_channels + n_analogs + counter))
        """
        total_channels = counter + n_channels + n_analogs
        with h5py.File(path, "r") as file:
            data = file['data'][()]
            n_samples = len(data) // total_channels
            data = np.reshape(data, (n_samples, total_channels))
        return n_samples, data


    def parse_h5_log(path):
        """Parse parameters from an HDF5 data file.

        Parameters
        ----------
        path : str
            path to HDF5 file

        Returns
        -------
        parameters
            dictionnary of parsed parameters
        options
            dictionnary of parsed optional parameters
        """
        with h5py.File(path, mode="r") as file:
            parameters = {}
            for key in file["parameters"]:
                try:
                    dset = file["parameters"][key].asstr()
                    parameters[key] = dset[()]
                except TypeError:
                    parameters[key] = file["parameters"][key][()]
            options = {}
            for key in file["options"]:
                try:
                    dset = file["options"][key].asstr()
                    options[key] = dset[()]
                except TypeError:
                    options[key] = file["options"][key][()]
        return parameters, options
    
    __allowed_ext__.update({
        ".h5": H5File,
        ".hdf5": H5File,   
    })

except ModuleNotFoundError as e:
    # IF H5PY IS NOT INSTALLED
    message = """Seems like 'h5py' is not installed in the current environment.
    Errors may occurs in using some IO tools.
    Please consider installing the package 'h5py' via 'pip'.
    """
    warnings.warn(message, MegamicrosIOWarning)


class File():
    def __new__(cls, path, mode="r"):
        path = add_date_to_filename(path)
        if osp.exists("./recording"):
            path = osp.join("./recording", path)
        _, ext = detect_extension(path)
        if ext in __allowed_ext__:
            return __allowed_ext__[ext](path, mode)


if __name__ == "__main__":
    filename = "/home/hugo/test"
    path = add_date_to_filename(filename)
    print(path)

    filename2 = "/home/hugo/Documents/Dev/Megamicros/megamicros/recording_20210506_16:26:43.dat"
    date, hours, name = parse_filename(filename2)
    print(date)
    print(hours)
    print(name)
    
    parameters = dict(
        n_channels=89,
        n_analogs=0,
        counter=1,
        samplingrate=50000,
        dtype="int32",
        duration=5,
    )
    datfile = DatFile("test.dat", mode="w")
    datfile.open()
    datfile.dump_log(parameters, message="test hello", options={"speed":50})
    datfile.close()

    out_log = parse_log("test.log")
    print(out_log)

    recording_h5 = "/home/hugo/Documents/Dev/Megamicros/megamicros/test_20210509_15:05:20.h5"
    out_h5_log = parse_h5_log(recording_h5)
    print(out_h5_log)
