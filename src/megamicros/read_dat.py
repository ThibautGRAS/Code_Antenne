from fileinput import filename
import numpy as np
import pylab as plt

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

if __name__ == "__main__" :
    filename = "C:/Users/leblancc/Desktop/essai2.dat"
    N , data = read_dat(filename, 8)
    plt.figure()
    # plt.plot(data[:,0]) # vérifie le compteur
    plt.plot(data[:,1:]) 
    plt.show()