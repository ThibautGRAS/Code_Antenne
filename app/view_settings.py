# -*- coding: utf-8 -*-
"""Reglages d'affichage 3D partages (menu Affichage <-> rendu), modifiables a chaud."""


class _ViewSettings:
    def __init__(self):
        self.cmap = "turbo"   # palette de la carte SPL
        self.ssao = True      # occlusion ambiante
        self.pbr = True        # materiau satine
        self.halo = True       # halo sur le point chaud
        self.opacity = 1.0     # opacite de la carte SPL (1 = opaque = net, defaut)
        # Fond + axes du viewport 3D (mis a jour selon le theme clair/sombre)
        self.bg = "#16273F"
        self.bg_top = "#0B1626"
        self.fg = "#B8C4D6"

    def set_theme(self, name):
        if name == "Clair":
            self.bg, self.bg_top, self.fg = "#FFFFFF", "#EEF2F7", "#5B6672"
        else:
            self.bg, self.bg_top, self.fg = "#16273F", "#0B1626", "#B8C4D6"


VIEW = _ViewSettings()

CMAPS = ["turbo", "jet", "inferno", "viridis"]
