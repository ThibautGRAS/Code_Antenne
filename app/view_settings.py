# -*- coding: utf-8 -*-
"""Reglages d'affichage 3D partages (menu Affichage <-> rendu), modifiables a chaud."""


class _ViewSettings:
    def __init__(self):
        self.cmap = "turbo"   # palette de la carte SPL
        self.ssao = True      # occlusion ambiante
        self.pbr = True        # materiau satine
        self.halo = True       # halo sur le point chaud


VIEW = _ViewSettings()

CMAPS = ["turbo", "jet", "inferno", "viridis"]
