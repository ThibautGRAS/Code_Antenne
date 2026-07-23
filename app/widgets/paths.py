# -*- coding: utf-8 -*-
"""Memoire des derniers dossiers utilises dans les dialogues de fichier.

Utilise QSettings (stockage OS : base de registre sous Windows) -> aucun fichier
ecrit dans le depot. Permet de rouvrir chaque dialogue au dernier endroit choisi.
"""

import os

from PySide6.QtCore import QSettings


def _settings():
    return QSettings("AntenneMu", "PosteOffline")


def last_dir(key, default=""):
    return _settings().value(f"lastdir/{key}", default) or default


def remember_dir(key, path):
    """Memorise le dossier de `path` (path peut etre un fichier ou un dossier)."""
    if not path:
        return
    d = path if os.path.isdir(path) else os.path.dirname(path)
    if d:
        _settings().setValue(f"lastdir/{key}", d)
