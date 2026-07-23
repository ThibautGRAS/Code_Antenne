# -*- coding: utf-8 -*-
"""Console de logs + barre de progression + bouton Arreter (calcul en sous-processus)."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QProgressBar, QLabel, QPushButton,
)


class LogConsole(QWidget):
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.status = QLabel("Pret.")
        self.btn_stop = QPushButton("Arreter")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_requested)
        top.addWidget(self.status, 1)
        top.addWidget(self.btn_stop)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)

        lay.addLayout(top)
        lay.addWidget(self.bar)
        lay.addWidget(self.out, 1)

    def start(self, msg="Calcul en cours..."):
        self.status.setText(msg)
        self.bar.setRange(0, 0)  # mode indetermine

    def stop(self, msg="Termine."):
        self.status.setText(msg)
        self.bar.setRange(0, 1)
        self.bar.setValue(1)

    def append(self, text):
        for line in str(text).splitlines():
            self.out.appendPlainText(line)

    def clear(self):
        self.out.clear()
