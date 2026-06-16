#!/usr/bin/env python3
# -*- coding: utf-8 -*-


"""
.. include:: doc/index.md
"""


import os
from .system import System, allowed_devices, alloc_channels
#from .interactive import Callbacks, LiveRecording, read


os.makedirs("./recording", exist_ok=True)
