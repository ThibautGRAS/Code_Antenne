#!/usr/bin/env python

# Read module version from init file
with open('ldsfdatareader/__init__.py') as f:
    for line in f:
        if line.startswith('__version__'):
            exec(line)

from distutils.core import setup
setup(name='ldsfdatareader',
      version=__version__,
      description='Python module to read .ldsf files',
      long_description=open('README.txt').read(),
      license='MIT',
      packages=['ldsfdatareader'],
     )
