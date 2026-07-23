# -*- coding: utf-8 -*-
"""Console de logs + barre de progression (indeterminee pendant le calcul)."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPlainTextEdit, QProgressBar, QLabel,
)


class LogConsole(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.status = QLabel("Pret.")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)

        lay.addWidget(self.status)
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
