# -*- coding: utf-8 -*-
"""
Interface graphique "poste de travail" pour les traitements OFFLINE d'AntenneMu.

Appli PySide6 autonome (dossier `app/`, indEpendante de `src/live`) : permet a
n'importe qui de lancer les workflows offline (beamforming 3D, niveaux/puissance,
calibration) sans editer de code.

L'appli ORCHESTRE : elle appelle les fonctions de `src/` via des sous-processus
(cf. app/runner.py + app/workflows/), sans reimplementer ni modifier le calcul.

Lancement :  python -m app        (depuis la racine du depot, venv active)
"""
