# -*- coding: utf-8 -*-
"""Scripts d'execution headless des workflows (lances en sous-processus par l'appli).

Chacun lit un JSON de parametres, construit Config(overrides=...) et appelle les
fonctions de src/ (aucune logique dupliquee), puis ouvre la visualisation.
"""
