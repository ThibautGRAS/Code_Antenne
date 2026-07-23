# -*- coding: utf-8 -*-
"""Petite pop-up contenant un ParamForm (reglages avances : scale / offsets...)."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox


class ParamDialog(QDialog):
    def __init__(self, title, form, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)
        lay = QVBoxLayout(self)
        lay.addWidget(form)
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.accept)
        btns.accepted.connect(self.accept)
        lay.addWidget(btns)
