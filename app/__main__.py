# -*- coding: utf-8 -*-
"""Point d'entree : `python -m app`.

Le GUI est du PySide6 PUR (il n'importe ni matplotlib, ni pyvista, ni src/*) :
tout le calcul + la visu tournent dans des sous-processus (cf. app/runner.py).
"""

import os

# Liaison Qt unique (PySide6/Qt6) pour matplotlib(QtAgg) et pyvista/pyvistaqt, et
# backend matplotlib interactif compatible -- a poser AVANT tout import de ces libs
# (l'affichage embarque de l'etape 3 les charge a la demande).
os.environ.setdefault("QT_API", "pyside6")
os.environ.setdefault("MPLBACKEND", "QtAgg")

import sys

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
