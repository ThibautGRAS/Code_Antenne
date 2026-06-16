ldsfdatareader
============

Siemens LMS produces hardware and software for test measurement, data aquisition, 
and storage. Data files are stored with the extension .ldsf in a proprietary
format.

This is a Python module to read .ldsf files

Installation
------------

The module is available locally on file://ldsfdatareader so all
one needs to do is:

::

    python setup.py install

Example usage
-------------

Scripts like the following may be run from the command line or, more
interactively, from `Jupyter Notebook <http://jupyter.org>`_

.. code:: python

    import ldsfdatareader as ldr
    with ldr.open('myfile.ldsf') as ldsf:
        print(ldsf.info)
        print(list(ldsf.keys()))
        for ch in ldsf.channels:
            print(ch)
        ch = 1 # or ch = 'chname1'
        sr = ldsf[voie].series()
        unit = ldsf[voie].unit
        ax = sr.plot()
        ax.set_ylabel(unit)

Contribute
----------

Bug reports and pull requests should be directed to Nicolas Bedouin
