# -*- coding: utf-8 -*-
"""Execution d'un workflow en SOUS-PROCESSUS (QProcess), sans figer l'UI.

On lance `python <script> <params.json>`. Le sous-processus est un equivalent CLI
(il ouvre la visu matplotlib/pyvista comme les mains) : aucun conflit de liaison Qt
avec l'appli PySide6 parente, et l'UI reste reactive. La sortie est streamee vers
la console de logs via le signal `output`.
"""

import os
import sys
import json
import tempfile

from PySide6.QtCore import QObject, QProcess, Signal


class WorkflowRunner(QObject):
    output = Signal(str)
    started = Signal()
    finished = Signal(int)  # code de retour du sous-processus

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None
        self._params_path = None

    @property
    def running(self):
        return self._proc is not None and self._proc.state() != QProcess.NotRunning

    def run(self, script_path, params):
        """Ecrit `params` dans un JSON temporaire et lance `python script_path json`."""
        if self.running:
            return

        fd, self._params_path = tempfile.mkstemp(suffix=".json", prefix="antennemu_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False)

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)  # stdout + stderr
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_finished)
        self._proc.setProgram(sys.executable)
        self._proc.setArguments([script_path, self._params_path])
        self.started.emit()
        self._proc.start()

    def stop(self):
        if self.running:
            self._proc.kill()

    def _on_output(self):
        raw = bytes(self._proc.readAllStandardOutput()).decode("utf-8", "replace")
        if raw:
            self.output.emit(raw)

    def _on_finished(self, code, _status):
        self._cleanup()
        self.finished.emit(int(code))

    def _cleanup(self):
        if self._params_path and os.path.exists(self._params_path):
            try:
                os.remove(self._params_path)
            except OSError:
                pass
        self._params_path = None
