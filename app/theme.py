# -*- coding: utf-8 -*-
"""Theme moderne de l'appli (charte : navy encre, rouge accent, surfaces claires)."""

QSS = """
* { font-family: "Arial Nova", Arimo, Arial, Helvetica, sans-serif; }
QMainWindow, QWidget { background-color: #F4F6F9; color: #001E50; font-size: 13px; }

/* ---------- Barre superieure ---------- */
QFrame#TopBar { background: #FFFFFF; border: none; border-bottom: 3px solid #EF3346; }
QLabel#AppEyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#AppTitle { color: #001E50; font-size: 17px; font-weight: 700; }
QLabel#TopInfo { color: #5B6672; font-size: 12px; }

/* ---------- Barre laterale ---------- */
QFrame#Sidebar { background: #001E50; border: none; }
QLabel#Brand { color: #FFFFFF; font-size: 15px; font-weight: 700; letter-spacing: 2px; }
QLabel#BrandSub { color: #7F97BC; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QPushButton#Nav { text-align: left; border: none; border-radius: 8px; padding: 11px 14px;
                  margin: 2px 10px; background: transparent; color: #C9D6EA; font-size: 13px; }
QPushButton#Nav:hover { background: rgba(255,255,255,0.07); color: #FFFFFF; }
QPushButton#Nav:checked { background: #EF3346; color: #FFFFFF; font-weight: 700; }

/* ---------- Cartes ---------- */
QFrame#Card { background: #FFFFFF; border: 1px solid #E6EAF0; border-radius: 12px; }
QLabel#Eyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#CardTitle { color: #001E50; font-size: 14px; font-weight: 700; }
QLabel#CardSub { color: #8A9199; font-size: 11px; }
QLabel#Badge { background: #EF3346; color: #FFFFFF; border-radius: 13px;
               min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
               font-size: 13px; font-weight: 700; }

/* ---------- Boutons ---------- */
QPushButton { background: #FFFFFF; color: #001E50; border: 1px solid #C7CED8;
              border-radius: 8px; padding: 8px 14px; }
QPushButton:hover { border-color: #001E50; background: #EEF4FB; }
QPushButton:pressed { padding-top: 9px; padding-bottom: 7px; }
QPushButton:disabled { color: #AEB6BF; border-color: #E3E8EE; background: #F7F9FB; }
QPushButton#Run { background: #EF3346; color: #FFFFFF; border: none; border-radius: 8px;
                  padding: 10px 14px; font-weight: 700; }
QPushButton#Run:hover { background: #D92435; }
QPushButton#Run:disabled { background: #D7DBE0; color: #FFFFFF; }
QPushButton#Ghost { background: transparent; border: 1px solid #C7CED8; color: #001E50;
                    padding: 7px 12px; }
QPushButton#Ghost:hover { background: #EEF4FB; border-color: #001E50; }

/* ---------- Champs ---------- */
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

/* ---------- Logs (console sombre) ---------- */
QPlainTextEdit { background: #0E1B2E; color: #D6E2F2; border: 1px solid #E6EAF0;
                 border-radius: 10px; font-family: Consolas, "Cascadia Mono", monospace;
                 font-size: 12px; padding: 6px; }
QProgressBar { border: none; border-radius: 3px; background: #E6EAF0; max-height: 6px; }
QProgressBar::chunk { background-color: #EF3346; border-radius: 3px; }

/* ---------- Menus ---------- */
QMenuBar { background: transparent; }
QMenuBar::item { padding: 6px 12px; background: transparent; border-radius: 6px; }
QMenuBar::item:selected { background: #E1F6F9; }
QMenu { background: #FFFFFF; border: 1px solid #C7CED8; border-radius: 8px; }
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background: #EEF4FB; }

/* ---------- Divers ---------- */
QScrollArea { border: none; background: transparent; }
QLabel { background: transparent; }
QSplitter::handle { background: transparent; height: 6px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #C7CED8; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #9FB0C4; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #C7CED8; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""
