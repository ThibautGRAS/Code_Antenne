# -*- coding: utf-8 -*-
"""Theme sombre de l'appli (memes teintes que src/live/ui_qt, pour la coherence)."""

QSS = """
QWidget { background-color: rgb(5,28,55); color: rgb(235,240,245); font-size: 13px; }

QFrame#Sidebar { background-color: rgb(0,48,85);
                 border-right: 1px solid rgb(80,150,200); }
QLabel#Title { font-size: 18px; font-weight: bold; letter-spacing: 2px; }

QPushButton { background-color: rgb(8,42,78); border: 1px solid rgb(80,150,200);
              border-radius: 6px; padding: 6px 12px; }
QPushButton:hover { background-color: rgb(14,60,105); }

QPushButton#Nav { text-align: left; border: none; border-radius: 0;
                  padding: 12px 18px; background: transparent; }
QPushButton#Nav:hover { background-color: rgb(6,40,72); }
QPushButton#Nav:checked { background-color: rgb(8,42,78);
                          border-left: 3px solid rgb(90,170,230); font-weight: bold; }

QPushButton#Run { background-color: rgb(0,120,90); border-color: rgb(0,160,120);
                  font-weight: bold; padding: 8px 12px; }
QPushButton#Run:hover { background-color: rgb(0,150,110); }
QPushButton#Run:disabled { background-color: rgb(45,65,90); color: rgb(120,130,145);
                           border-color: rgb(45,65,90); }

QGroupBox { border: 1px solid rgb(80,150,200); border-radius: 8px; margin-top: 14px;
            font-weight: bold; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: rgb(12,32,52); border: 1px solid rgb(60,90,120);
    border-radius: 4px; padding: 4px 6px; }
QComboBox QAbstractItemView { background-color: rgb(12,32,52);
    selection-background-color: rgb(80,150,200); }

QPlainTextEdit { background-color: rgb(10,20,34); border: 1px solid rgb(45,65,90);
                 border-radius: 6px; font-family: Consolas, monospace; font-size: 12px; }

QProgressBar { border: 1px solid rgb(45,65,90); border-radius: 4px;
               background: rgb(12,32,52); max-height: 8px; text-align: center; }
QProgressBar::chunk { background-color: rgb(80,150,210); border-radius: 4px; }

QScrollArea { border: none; }
"""
