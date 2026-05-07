from __future__ import annotations

import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from kosim.simulation.engine import RunEvent


class RunStatusPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.started_at: float | None = None
        self.current_step = QLabel("-")
        self.status = QLabel("-")
        self.elapsed = QLabel("00:00:00")
        self.current_date = QLabel("-")
        layout = QFormLayout(self)
        layout.addRow("Current step", self.current_step)
        layout.addRow("Status", self.status)
        layout.addRow("Elapsed", self.elapsed)
        layout.addRow("Current date", self.current_date)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(500)

    def apply_event(self, event: RunEvent) -> None:
        if self.started_at is None:
            self.started_at = time.monotonic()
        self.current_step.setText(event.step)
        self.status.setText(event.status)
        if "date" in event.payload:
            self.current_date.setText(str(event.payload["date"]))

    def _tick(self) -> None:
        if self.started_at is None:
            return
        seconds = int(time.monotonic() - self.started_at)
        hours, rem = divmod(seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        self.elapsed.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
