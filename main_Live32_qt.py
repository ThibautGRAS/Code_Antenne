# -*- coding: utf-8 -*-
"""
main_qt.py — Point d'entree de l'interface PySide6 de la camera acoustique live.

Fichier volontairement MINCE : il ne fait que charger la config, creer la
QApplication et la fenetre. Toute l'UI est dans src/live/ui_qt.py et le moteur
dans src/live/live_engine.py (sur le meme modele que l'ancien main qui
deleguait l'affichage a src/live/display.py).

AFFICHAGE UNIQUEMENT : aucun calcul n'est modifie (moteur reutilise tel quel).
Repli simulation automatique si la carte MU32 / la camera sont absentes
(flags YAML force_sim_audio / force_sim_camera).

L'ancien main_Live32_newUI.py reste le fallback OpenCV, intact.
"""

import sys

from PySide6.QtWidgets import QApplication

from data.config_live import Config
from src.live.ui_qt import AcousticCameraWindow


def main():
    config = Config()
    app = QApplication(sys.argv)
    win = AcousticCameraWindow(config)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
