from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from kosim.pipeline import DailyPipelineRunner
from kosim.simulation.engine import RunEvent


STATUS_SYMBOLS = {
    "pending": "○",
    "running": "●",
    "success": "✓",
    "warning": "!",
    "failed": "×",
    "skipped": "-",
}


class ProgressTimeline(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.labels: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        for step in DailyPipelineRunner.STEPS:
            label = QLabel(f"{STATUS_SYMBOLS['pending']} {step}")
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.labels[step] = label
            layout.addWidget(label)
        layout.addStretch(1)

    def apply_event(self, event: RunEvent) -> None:
        label = self.labels.get(event.step)
        if not label:
            return
        symbol = STATUS_SYMBOLS.get(event.status, "?")
        label.setText(f"{symbol} {event.step}: {event.message}")
