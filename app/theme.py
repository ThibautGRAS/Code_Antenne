# -*- coding: utf-8 -*-
"""Theme de l'appli, d'apres la charte : navy encre, rouge accent, surfaces claires.

Palette : Navy #001E50 (encre/primaire), Rouge #EF3346 (accent), Cyan #E1F6F9 et
Rose #FCD9E0 (surfaces teintees), Gris froid #C1C7C6 (neutre), fond #F4F6F9 / blanc.
Fonctionnelles graphes : bleu #1F6FE0, orange #F08A24, vert #1F9D57.
"""

QSS = """
* { font-family: "Arial Nova", Arimo, Arial, Helvetica, sans-serif; }

QMainWindow, QWidget { background-color: #F4F6F9; color: #001E50; font-size: 13px; }

/* --- Barre de menu : filet de marque rouge 3px --- */
QMenuBar { background: #FFFFFF; color: #001E50; border-bottom: 3px solid #EF3346; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #E1F6F9; }
QMenu { background: #FFFFFF; border: 1px solid #C1C7C6; }
QMenu::item:selected { background: #E1F6F9; }

/* --- Barre laterale : navy, texte blanc --- */
QFrame#Sidebar { background-color: #001E50; border: none; }
QLabel#Title { color: #FFFFFF; font-size: 18px; font-weight: 700; letter-spacing: 2px; }
QPushButton#Nav { text-align: left; border: none; border-radius: 0; padding: 12px 18px;
                  background: transparent; color: #FFFFFF; }
QPushButton#Nav:hover { background: rgba(255,255,255,0.08); }
QPushButton#Nav:checked { background: rgba(255,255,255,0.14);
                          border-left: 3px solid #EF3346; font-weight: 700; }

/* --- Cartes / groupes : surface blanche, bord 2px, coins doux --- */
QGroupBox { background: #FFFFFF; border: 2px solid #C1C7C6; border-radius: 6px;
            margin-top: 14px; font-weight: 700; color: #001E50; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }

/* --- Boutons --- */
QPushButton { background: #FFFFFF; color: #001E50; border: 2px solid #C1C7C6;
              border-radius: 4px; padding: 6px 12px; }
QPushButton:hover { border-color: #001E50; background: #E1F6F9; }
QPushButton:pressed { padding-top: 7px; padding-bottom: 5px; }   /* descente 1px */
QPushButton:disabled { color: #9AA3A2; border-color: #DFE3E6; background: #F4F6F9; }

QPushButton#Run { background: #EF3346; color: #FFFFFF; border: 2px solid #EF3346;
                  font-weight: 700; padding: 8px 12px; }
QPushButton#Run:hover { background: #D92435; border-color: #D92435; }
QPushButton#Run:disabled { background: #C1C7C6; border-color: #C1C7C6; color: #FFFFFF; }

/* --- Champs --- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #FFFFFF; color: #001E50; border: 2px solid #C1C7C6;
    border-radius: 4px; padding: 4px 6px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #1F6FE0; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #001E50;
    selection-background-color: #E1F6F9; }

/* --- Logs / progression --- */
QPlainTextEdit { background: #FFFFFF; color: #001E50; border: 2px solid #C1C7C6;
                 border-radius: 6px; font-family: Consolas, monospace; font-size: 12px; }
QProgressBar { border: 1px solid #C1C7C6; border-radius: 4px; background: #F4F6F9;
               max-height: 8px; text-align: center; color: #001E50; }
QProgressBar::chunk { background-color: #EF3346; border-radius: 4px; }

QLabel { background: transparent; }
QScrollArea { border: none; background: transparent; }
QSplitter::handle { background: #C1C7C6; }
"""
