# -*- coding: utf-8 -*-
"""Theme sombre de l'appli (charte : encre navy, rouge accent).

Fond navy profond, surfaces (cartes / champs) en navy plus clair, texte clair,
accent rouge #EF3346, focus bleu #3B82F6.
"""

QSS = """
* { font-family: "Arial Nova", Arimo, Arial, Helvetica, sans-serif; }
QMainWindow, QWidget { background-color: #0E1B2E; color: #E7EEF7; font-size: 13px; }

/* ---------- Barre superieure ---------- */
QFrame#TopBar { background: #16273F; border: none; border-bottom: 3px solid #EF3346; }
QLabel#AppEyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QLabel#AppTitle { color: #FFFFFF; font-size: 17px; font-weight: 700; }
QLabel#TopInfo { color: #93A6C0; font-size: 12px; }

/* ---------- Barre laterale ---------- */
QFrame#Sidebar { background: #0A1524; border: none; }
QLabel#Brand { color: #FFFFFF; font-size: 15px; font-weight: 700; letter-spacing: 2px; }
QLabel#BrandSub { color: #6E86A8; font-size: 10px; font-weight: 700; letter-spacing: 2px; }
QPushButton#Nav { text-align: left; border: none; border-radius: 8px; padding: 11px 14px;
                  margin: 2px 10px; background: transparent; color: #C9D6EA; font-size: 13px; }
QPushButton#Nav:hover { background: rgba(255,255,255,0.06); color: #FFFFFF; }
QPushButton#Nav:checked { background: #EF3346; color: #FFFFFF; font-weight: 700; }

/* ---------- Cartes ---------- */
QFrame#Card { background: #16273F; border: 1px solid #26384F; border-radius: 12px; }
QLabel#Eyebrow { color: #EF3346; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }
QLabel#CardTitle { color: #FFFFFF; font-size: 14px; font-weight: 700; }
QLabel#CardSub { color: #93A6C0; font-size: 11px; }
QLabel#Badge { background: #EF3346; color: #FFFFFF; border-radius: 13px;
               min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
               font-size: 13px; font-weight: 700; }

/* ---------- Boutons ---------- */
QPushButton { background: #1C2F4C; color: #E7EEF7; border: 1px solid #33486A;
              border-radius: 8px; padding: 8px 14px; }
QPushButton:hover { border-color: #3B82F6; background: #223A5C; }
QPushButton:pressed { padding-top: 9px; padding-bottom: 7px; }
QPushButton:disabled { color: #5E718C; border-color: #24374E; background: #142335; }
QPushButton#Run { background: #EF3346; color: #FFFFFF; border: none; border-radius: 8px;
                  padding: 10px 14px; font-weight: 700; }
QPushButton#Run:hover { background: #D92435; }
QPushButton#Run:disabled { background: #3E4A5E; color: #93A6C0; }
QPushButton#Ghost { background: transparent; border: 1px solid #33486A; color: #C9D6EA;
                    padding: 7px 12px; }
QPushButton#Ghost:hover { background: #1C2F4C; border-color: #3B82F6; }

/* ---------- Champs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #1C2F4C; color: #E7EEF7; border: 1px solid #33486A; border-radius: 8px;
    padding: 6px 8px; min-height: 18px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 2px solid #3B82F6; }
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled { background: #142335; color: #5E718C; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView { background: #16273F; color: #E7EEF7; border: 1px solid #33486A;
    border-radius: 8px; selection-background-color: #223A5C; selection-color: #FFFFFF; outline: none; }
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 16px; border: none; background: transparent; }

/* ---------- Cases a cocher ---------- */
QCheckBox { color: #E7EEF7; spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #33486A;
                       border-radius: 5px; background: #1C2F4C; }
QCheckBox::indicator:hover { border-color: #3B82F6; }
QCheckBox::indicator:checked { background: #EF3346; border-color: #EF3346; }

/* ---------- Logs (console) ---------- */
QPlainTextEdit { background: #0A1524; color: #CFE0F2; border: 1px solid #26384F;
                 border-radius: 10px; font-family: Consolas, "Cascadia Mono", monospace;
                 font-size: 12px; padding: 6px; }
QProgressBar { border: none; border-radius: 3px; background: #22344F; max-height: 6px; }
QProgressBar::chunk { background-color: #EF3346; border-radius: 3px; }

/* ---------- Menus ---------- */
QMenuBar { background: transparent; }
QMenuBar::item { padding: 6px 12px; background: transparent; border-radius: 6px; }
QMenuBar::item:selected { background: #223A5C; }
QMenu { background: #16273F; color: #E7EEF7; border: 1px solid #33486A; border-radius: 8px; }
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background: #223A5C; }

/* ---------- Divers ---------- */
QScrollArea { border: none; background: transparent; }
QLabel { background: transparent; }
QSplitter::handle { background: transparent; height: 6px; }
QToolTip { background: #16273F; color: #E7EEF7; border: 1px solid #33486A; padding: 4px 6px; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #33486A; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4A628A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: #33486A; border-radius: 5px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #4A628A; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""
