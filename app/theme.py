# -*- coding: utf-8 -*-
"""Themes de l'appli, alignes sur la charte : plat, editorial, net.

Principes charte : navy encre #001E50, rouge accent #EF3346, surfaces claires (clair) ou
navy (sombre) ; rayons faibles (4-6 px) ; filets nets (1 px filets, 3 px rouge de marque) ;
ombres sobres teintees navy (jamais noires) ; PAS de degrades ni d'effets skeuomorphes.
Sombre (defaut) + Clair, sidebar navy et console sombre communes.
"""

# ------------------------------------------------------------------ commun
_COMMON = """
* { font-family: "Arial Nova", Arimo, Arial, Helvetica, sans-serif; }

QFrame#TopBar { border: none; border-bottom: 3px solid #EF3346; }
QLabel#AppTitle { font-size: 18px; font-weight: 700; letter-spacing: 0.3px; }

QFrame#Sidebar { background: #0A1524; border: none; }
QFrame#SideHead { background: #0A1524; border-bottom: 1px solid #22344F; }
QLabel#Logo { background: #FFFFFF; border-radius: 4px; padding: 6px 8px; }
QLabel#Brand { color: #FFFFFF; font-size: 15px; font-weight: 700; letter-spacing: 2px; }
QPushButton#Nav { text-align: left; border: none; border-radius: 4px; padding: 11px 14px;
                  margin: 2px 10px; background: transparent; color: #C9D6EA; font-size: 13px; }
QPushButton#Nav:hover { background: rgba(255,255,255,0.06); color: #FFFFFF; }
QPushButton#Nav:checked { background: #EF3346; color: #FFFFFF; font-weight: 700; }

QWidget#CardHead { background: transparent; }
QLabel#Eyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#CardTitle { font-size: 14px; font-weight: 700; }
QLabel#Chevron { color: #7C8CA5; font-size: 12px; }
QLabel#Badge { background: #EF3346; color: #FFFFFF; border-radius: 13px;
               min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
               font-size: 13px; font-weight: 700; }
QLabel#SourceLabel { font-weight: 700; }

QPushButton#Run { background: #EF3346; color: #FFFFFF; border: none; border-radius: 4px;
                  padding: 10px 14px; font-weight: 700; }
QPushButton#Run:hover { background: #D92435; }
QPushButton#Run:pressed { padding-top: 11px; padding-bottom: 9px; }   /* descente 1px (charte) */

QTextBrowser { background: #0A1524; color: #E7EEF7; border: 1px solid #26384F;
               border-radius: 6px; padding: 12px; font-size: 13px; }

QSlider::groove:horizontal { height: 4px; background: #46608A; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #EF3346; border-radius: 2px; }
QSlider::add-page:horizontal { background: #46608A; border-radius: 2px; }
QSlider::handle:horizontal { background: #FFFFFF; border: 2px solid #EF3346;
                             width: 13px; height: 13px; margin: -6px 0; border-radius: 8px; }

QProgressBar { border: none; border-radius: 2px; background: #22344F; max-height: 5px; }
QProgressBar::chunk { background-color: #EF3346; border-radius: 2px; }

QScrollArea { border: none; background: transparent; }
QLabel { background: transparent; }
QSplitter::handle { background: transparent; height: 6px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #7C8CA5; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9FB0C4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #7C8CA5; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""

# ------------------------------------------------------------------ sombre
QSS_DARK = _COMMON + """
QMainWindow, QWidget { background-color: #0B1626; color: #E7EEF7; font-size: 13px; }
QFrame#TopBar { background: #16273F; }
QLabel#AppTitle { color: #FFFFFF; }
QLabel#AppSub { color: #93A6C0; font-size: 11px; letter-spacing: 0.5px; }
QLabel#TopInfo { color: #93A6C0; font-size: 12px; }

QFrame#Card { background: #16273F; border: 1px solid #2A3F63; border-radius: 6px; }
QFrame#ResultPanel { background: #16273F; border: none; border-radius: 6px; }
QLabel#CardTitle { color: #FFFFFF; }
QLabel#CardSub { color: #93A6C0; font-size: 11px; }

QPushButton { background: #223A5C; color: #E7EEF7; border: 1px solid #38517A;
              border-radius: 4px; padding: 8px 14px; }
QPushButton:hover { background: #2A4670; border-color: #4E7BC0; }
QPushButton:pressed { padding-top: 9px; padding-bottom: 7px; }
QPushButton:disabled { color: #66798F; border-color: #2A3E57; background: #172740; }
QPushButton#Run:disabled { background: #46536B; color: #A9B6C9; }
QPushButton#Ghost { background: transparent; border: 1px solid #38517A; color: #C9D6EA;
                    border-radius: 4px; padding: 7px 12px; }
QPushButton#Ghost:hover { background: #223A5C; border-color: #4E7BC0; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #223A5C; color: #E7EEF7; border: 1px solid #38517A; border-radius: 4px;
    padding: 6px 8px; min-height: 18px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #4E7BC0; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #172740; color: #66798F; }
QComboBox QAbstractItemView { background: #16273F; color: #E7EEF7; border: 1px solid #38517A;
    selection-background-color: #2A4670; selection-color: #FFFFFF; outline: none; }

QCheckBox { color: #E7EEF7; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #38517A; border-radius: 3px; background: #223A5C; }
QCheckBox::indicator:hover { border-color: #4E7BC0; }
QCheckBox::indicator:checked { background: #EF3346; border-color: #EF3346; }

QMenuBar { background: #16273F; color: #E7EEF7; }
QMenuBar::item { padding: 9px 14px; background: transparent; }
QMenuBar::item:selected { background: #2A4670; border-radius: 4px; }
QMenu { background: #16273F; color: #E7EEF7; border: 1px solid #38517A; border-radius: 6px; }
QMenu::item { padding: 7px 22px; }
QMenu::item:selected { background: #2A4670; }
QMenu::separator { height: 1px; background: #38517A; margin: 4px 8px; }
QToolTip { background: #16273F; color: #E7EEF7; border: 1px solid #38517A; padding: 4px 6px; border-radius: 4px; }
"""

# ------------------------------------------------------------------ clair
QSS_LIGHT = _COMMON + """
QMainWindow, QWidget { background-color: #F4F6F9; color: #001E50; font-size: 13px; }
QFrame#TopBar { background: #FFFFFF; }
QLabel#AppTitle { color: #001E50; }
QLabel#AppSub { color: #5B6672; font-size: 11px; letter-spacing: 0.5px; }
QLabel#TopInfo { color: #5B6672; font-size: 12px; }

QFrame#Card { background: #FFFFFF; border: 1px solid #D8DEE7; border-radius: 6px; }
QFrame#ResultPanel { background: #FFFFFF; border: none; border-radius: 6px; }
QLabel#CardTitle { color: #001E50; }
QLabel#CardSub { color: #8A9199; font-size: 11px; }

QPushButton { background: #FFFFFF; color: #001E50; border: 1px solid #C1C7C6;
              border-radius: 4px; padding: 8px 14px; }
QPushButton:hover { background: #EEF4FB; border-color: #001E50; }
QPushButton:pressed { padding-top: 9px; padding-bottom: 7px; }
QPushButton:disabled { color: #AEB6BF; border-color: #E3E8EE; background: #F7F9FB; }
QPushButton#Run:disabled { background: #D7DBE0; color: #FFFFFF; }
QPushButton#Ghost { background: transparent; border: 1px solid #C1C7C6; color: #001E50;
                    border-radius: 4px; padding: 7px 12px; }
QPushButton#Ghost:hover { background: #EEF4FB; border-color: #001E50; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #FFFFFF; color: #001E50; border: 1px solid #C1C7C6; border-radius: 4px;
    padding: 6px 8px; min-height: 18px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #1F6FE0; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #F4F6F9; color: #AEB6BF; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #001E50; border: 1px solid #C1C7C6;
    selection-background-color: #EEF4FB; selection-color: #001E50; outline: none; }

QCheckBox { color: #001E50; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #C1C7C6; border-radius: 3px; background: #FFFFFF; }
QCheckBox::indicator:hover { border-color: #1F6FE0; }
QCheckBox::indicator:checked { background: #EF3346; border-color: #EF3346; }

QMenuBar { background: #FFFFFF; color: #001E50; }
QMenuBar::item { padding: 9px 14px; background: transparent; }
QMenuBar::item:selected { background: #E1F6F9; border-radius: 4px; }
QMenu { background: #FFFFFF; color: #001E50; border: 1px solid #C1C7C6; border-radius: 6px; }
QMenu::item { padding: 7px 22px; }
QMenu::item:selected { background: #EEF4FB; }
QMenu::separator { height: 1px; background: #E3E8EE; margin: 4px 8px; }
QToolTip { background: #FFFFFF; color: #001E50; border: 1px solid #C1C7C6; padding: 4px 6px; border-radius: 4px; }
"""

# QLabel transparent EN DERNIER (sinon la regle QWidget{background} du theme, de meme
# specificite mais declaree apres, fait peindre le fond de fenetre aux labels).
_TAIL = "\nQLabel { background: transparent; }\n"
QSS_DARK = QSS_DARK + _TAIL
QSS_LIGHT = QSS_LIGHT + _TAIL

THEMES = {"Sombre": QSS_DARK, "Clair": QSS_LIGHT}
QSS = QSS_DARK  # defaut / compat
