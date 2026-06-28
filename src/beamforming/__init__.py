# -*- coding: utf-8 -*-
"""
Package beamforming.

Import PARESSEUX (PEP 562) : les sous-modules ne sont PAS importés au chargement du
package. Un nom de niveau package (ex. `beamforming.plot_beamforming`) est résolu à
la première utilisation, en important le 1er sous-module qui le définit.

Pourquoi : le chemin LIVE n'utilise que `beamforming_signal` (calcul pur). Sans import
paresseux, charger ce package tirait toute la visu offline (matplotlib, pyvista, vtk)
inutilement dans l'appli temps réel. Les imports directs de sous-module
(`from src.beamforming.beamforming_X import ...`) continuent de fonctionner.
"""

import importlib

# Du plus léger (calcul pur) au plus lourd (visu : matplotlib / pyvista / vtk).
_SUBMODULES = (
    "beamforming_signal",
    "beamforming_timefocus",
    "beamforming_process",
    "beamforming_mesh",
    "beamforming_visu",
)


def __getattr__(name):
    """Résout `name` via le 1er sous-module qui le définit (import à la demande)."""
    for modname in _SUBMODULES:
        module = importlib.import_module(f"{__name__}.{modname}")
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value  # cache pour les accès suivants
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(globals())