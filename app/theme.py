# -*- coding: utf-8 -*-
"""Themes de l'appli (charte : encre navy, rouge accent). Sombre (defaut) + Clair.

Barre laterale navy et console de logs sombre dans les deux ; seule la zone de contenu
bascule clair/sombre.
"""

# Commun aux deux themes : sidebar navy, badge/eyebrow rouges, logs sombres, scrollbars.
_COMMON = """
* { font-family: "Arial Nova", Arimo, Arial, Helvetica, sans-serif; }

QFrame#TopBar { border: none; border-bottom: 3px solid #EF3346; }
QLabel#AppEyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#AppTitle { font-size: 17px; font-weight: 700; }

QFrame#Sidebar { background: #0A1524; border: none; }
QFrame#SideHead { background: #0A1524; border-bottom: 1px solid #22344F; }
QLabel#Logo { background: #FFFFFF; border-radius: 6px; padding: 6px 8px; }
QPushButton#Nav { text-align: left; border: none; border-radius: 8px; padding: 11px 14px;
                  margin: 2px 10px; background: transparent; color: #C9D6EA; font-size: 13px; }
QPushButton#Nav:hover { background: rgba(255,255,255,0.06); color: #FFFFFF; }
QPushButton#Nav:checked { background: #EF3346; color: #FFFFFF; font-weight: 700; }

QWidget#CardHead { background: transparent; }
QLabel#Chevron { color: #93A6C0; font-size: 13px; }
QLabel#Eyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }

QSlider::groove:horizontal { height: 4px; background: #46608A; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #EF3346; border-radius: 2px; }
QSlider::add-page:horizontal { background: #46608A; border-radius: 2px; }
QSlider::handle:horizontal { background: #FFFFFF; border: 2px solid #EF3346;
                             width: 14px; height: 14px; margin: -6px 0; border-radius: 9px; }
QSlider::handle:horizontal:hover { background: #FCD9E0; }
QLabel#Badge { background: #EF3346; color: #FFFFFF; border-radius: 13px;
               min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
               font-size: 13px; font-weight: 700; }
QLabel#SourceLabel { font-weight: 700; }

QPushButton#Run { background: #EF3346; color: #FFFFFF; border: none; border-radius: 8px;
                  padding: 10px 14px; font-weight: 700; }
QPushButton#Run:hover { background: #D92435; }

QPlainTextEdit { background: #071120; color: #CFE0F2; border: 1px solid #24374E;
                 border-radius: 10px; font-family: Consolas, "Cascadia Mono", monospace;
                 font-size: 12px; padding: 6px; }
QProgressBar { border: none; border-radius: 3px; background: #22344F; max-height: 6px; }
QProgressBar::chunk { background-color: #EF3346; border-radius: 3px; }

QCheckBox::indicator:checked { background: #EF3346; border-color: #EF3346; }

QScrollArea { border: none; background: transparent; }
QLabel { background: transparent; }
QSplitter::handle { background: transparent; height: 6px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #7C8CA5; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9FB0C4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #7C8CA5; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""

QSS_DARK = _COMMON + """
QMainWindow, QWidget { background-color: #0B1626; color: #E7EEF7; font-size: 13px; }
QFrame#TopBar { background: #1A2C48; }
QLabel#AppTitle { color: #FFFFFF; }
QLabel#TopInfo { color: #93A6C0; font-size: 12px; }

QFrame#Card { background: #1A2C48; border: 1px solid #2E466E; border-radius: 12px; }
QLabel#CardTitle { color: #FFFFFF; font-size: 14px; font-weight: 700; }
QLabel#CardSub { color: #93A6C0; font-size: 11px; }

QPushButton { background: #243B60; color: #E7EEF7; border: 1px solid #3A537C;
              border-radius: 8px; padding: 8px 14px; }
QPushButton:hover { border-color: #3B82F6; background: #2C4670; }
QPushButton:pressed { padding-top: 9px; padding-bottom: 7px; }
QPushButton:disabled { color: #66798F; border-color: #2A3E57; background: #172740; }
QPushButton#Run:disabled { background: #46536B; color: #A9B6C9; }
QPushButton#Ghost { background: transparent; border: 1px solid #3A537C; color: #C9D6EA; padding: 7px 12px; }
QPushButton#Ghost:hover { background: #243B60; border-color: #3B82F6; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #243B60; color: #E7EEF7; border: 1px solid #3A537C; border-radius: 8px;
    padding: 6px 8px; min-height: 18px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 2px solid #3B82F6; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #172740; color: #66798F; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #1A2C48; color: #E7EEF7; border: 1px solid #3A537C;
    border-radius: 8px; selection-background-color: #2C4670; selection-color: #FFFFFF; outline: none; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 16px; border: none; background: transparent; }

QCheckBox { color: #E7EEF7; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #3A537C; border-radius: 5px; background: #243B60; }
QCheckBox::indicator:hover { border-color: #3B82F6; }

QMenuBar { background: #1A2C48; color: #E7EEF7; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #2C4670; border-radius: 6px; }
QMenu { background: #1A2C48; color: #E7EEF7; border: 1px solid #3A537C; border-radius: 8px; }
QMenu::item { padding: 6px 22px; }
QMenu::item:selected { background: #2C4670; }
QMenu::separator { height: 1px; background: #3A537C; margin: 4px 8px; }
QToolTip { background: #1A2C48; color: #E7EEF7; border: 1px solid #3A537C; padding: 4px 6px; }
"""

QSS_LIGHT = _COMMON + """
QMainWindow, QWidget { background-color: #F4F6F9; color: #001E50; font-size: 13px; }
QFrame#TopBar { background: #FFFFFF; }
QLabel#AppTitle { color: #001E50; }
QLabel#TopInfo { color: #5B6672; font-size: 12px; }

QFrame#Card { background: #FFFFFF; border: 1px solid #E6EAF0; border-radius: 12px; }
QLabel#CardTitle { color: #001E50; font-size: 14px; font-weight: 700; }
QLabel#CardSub { color: #8A9199; font-size: 11px; }

QPushButton { background: #FFFFFF; color: #001E50; border: 1px solid #C7CED8;
              border-radius: 8px; padding: 8px 14px; }
QPushButton:hover { border-color: #001E50; background: #EEF4FB; }
QPushButton:pressed { padding-top: 9px; padding-bottom: 7px; }
QPushButton:disabled { color: #AEB6BF; border-color: #E3E8EE; background: #F7F9FB; }
QPushButton#Run:disabled { background: #D7DBE0; color: #FFFFFF; }
QPushButton#Ghost { background: transparent; border: 1px solid #C7CED8; color: #001E50; padding: 7px 12px; }
QPushButton#Ghost:hover { background: #EEF4FB; border-color: #001E50; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #FFFFFF; color: #001E50; border: 1px solid #C7CED8; border-radius: 8px;
    padding: 6px 8px; min-height: 18px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 2px solid #1F6FE0; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #F4F6F9; color: #AEB6BF; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #001E50; border: 1px solid #C7CED8;
    border-radius: 8px; selection-background-color: #EEF4FB; selection-color: #001E50; outline: none; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 16px; border: none; background: transparent; }

QCheckBox { color: #001E50; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #C7CED8; border-radius: 5px; background: #FFFFFF; }
QCheckBox::indicator:hover { border-color: #1F6FE0; }

QMenuBar { background: #FFFFFF; color: #001E50; }
QMenuBar::item { padding: 6px 12px; background: transparent; }
QMenuBar::item:selected { background: #E1F6F9; border-radius: 6px; }
QMenu { background: #FFFFFF; color: #001E50; border: 1px solid #C7CED8; border-radius: 8px; }
QMenu::item { padding: 6px 22px; }
QMenu::item:selected { background: #EEF4FB; }
QMenu::separator { height: 1px; background: #E3E8EE; margin: 4px 8px; }
QToolTip { background: #FFFFFF; color: #001E50; border: 1px solid #C7CED8; padding: 4px 6px; }
"""

# Priorite : QLabel transparent DOIT venir apres la regle QWidget{background} du theme
# (meme specificite -> la derniere gagne), sinon les labels peignent le fond de fenetre.
_TAIL = "\nQLabel { background: transparent; }\n"
QSS_DARK = QSS_DARK + _TAIL
QSS_LIGHT = QSS_LIGHT + _TAIL

THEMES = {"Sombre": QSS_DARK, "Clair": QSS_LIGHT}
QSS = QSS_DARK  # defaut / compat
