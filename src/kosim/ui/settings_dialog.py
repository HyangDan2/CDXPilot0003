from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from kosim.config import AppConfig
from kosim.data.availability import recent_complete_days
from kosim.data.storage import SQLiteStore
from kosim.integration_tests import test_kis_rest, test_llm, test_telegram


class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Integrated Settings")
        self.resize(780, 720)
        self.config_path = Path(config.path)
        self.values = copy.deepcopy(config.values)
        self.fields: dict[str, Any] = {}

        self.tabs = QTabWidget()
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(120)

        self._build_tabs()
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply_to_values)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(QLabel("Status"))
        layout.addWidget(self.status)
        layout.addWidget(buttons)

    def result_config(self) -> AppConfig:
        self.apply_to_values()
        return AppConfig(path=self.config_path, values=self.values)

    def _build_tabs(self) -> None:
        self.tabs.addTab(self._general_tab(), "General")
        self.tabs.addTab(self._kis_tab(), "KIS REST")
        self.tabs.addTab(self._telegram_tab(), "Telegram")
        self.tabs.addTab(self._llm_tab(), "LLM")
        self.tabs.addTab(self._market_tab(), "Market")
        self.tabs.addTab(self._simulation_tab(), "Simulation")
        self.tabs.addTab(self._data_tab(), "Data")
        self.tabs.addTab(self._schedule_tab(), "Schedule")

    def _general_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._combo(form, "app.mode", ["mock", "kis_rest"])
        self._line(form, "app.timezone")
        self._combo(form, "app.log_level", ["DEBUG", "INFO", "WARNING", "ERROR"])
        return widget

    def _kis_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._check(form, "kis.is_paper")
        self._line(form, "kis.base_url")
        self._line(form, "kis.paper_base_url")
        self._line(form, "kis.app_key")
        self._line(form, "kis.app_secret", password=True)
        self._line(form, "kis.account_no")
        self._line(form, "kis.token_cache_path")
        self._button(form, "Test KIS REST", self._test_kis)
        return widget

    def _telegram_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._check(form, "telegram.enabled")
        self._line(form, "telegram.bot_token", password=True)
        self._line(form, "telegram.chat_id")
        self._check(form, "telegram.delivery.send_raw_markdown_files")
        self._check(form, "telegram.delivery.send_llm_report_as_text")
        self._check(form, "telegram.delivery.send_llm_report_file")
        self._spin(form, "telegram.text.chunk_size", 500, 4000)
        self._check(form, "telegram.charts.send_summary_charts")
        self._check(form, "telegram.charts.send_case_charts")
        self._spin(form, "telegram.charts.case_chart_send_limit", 0, 200)
        self._button(form, "Test Telegram", self._test_telegram)
        return widget

    def _llm_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._check(form, "llm.enabled")
        self._line(form, "llm.provider")
        self._line(form, "llm.base_url")
        self._line(form, "llm.api_key", password=True)
        self._line(form, "llm.model")
        self._double(form, "llm.temperature", 0.0, 2.0, 2)
        self._spin(form, "llm.timeout_seconds", 1, 1000)
        self._spin(form, "llm.max_output_tokens", 1, 50000)
        self._spin(form, "llm.context_budget.max_prompt_chars", 10000, 1000000)
        self._spin(form, "llm.context_budget.max_bridge_chars", 1000, 500000)
        self._spin(form, "llm.context_budget.max_raw_summary_chars", 1000, 500000)
        self._spin(form, "llm.context_budget.max_sweep_csv_chars", 1000, 500000)
        self._button(form, "Test LLM", self._test_llm)
        return widget

    def _market_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._line(form, "market.universe.source")
        self._spin(form, "market.universe.top_n", 1, 30)
        self._line(form, "market.nxt.signal_times", transform=lambda v: ", ".join(v or []))
        self._line(form, "market.futures.symbol")
        self._combo(form, "market.futures.entry_side", ["long", "short"])
        return widget

    def _simulation_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._combo(form, "simulation.date_selection.mode", ["date_range", "recent_complete_data_days", "stored_snapshots"])
        self._spin(form, "simulation.date_selection.recent_complete_days", 1, 1000)
        self._line(form, "simulation.date_range.start")
        self._line(form, "simulation.date_range.end")
        self._line(form, "simulation.historical_signal_time")
        self._line(form, "simulation.signal_condition.rule")
        self._double(form, "simulation.signal_condition.positive_threshold_pct", -30.0, 30.0, 3)
        self._spin(form, "simulation.signal_condition.min_positive_count", 1, 30)
        self._line(form, "simulation.exit_sweep.start")
        self._line(form, "simulation.exit_sweep.end")
        self._spin(form, "simulation.exit_sweep.interval_minutes", 1, 240)
        self._double(form, "simulation.costs.fee_rate", 0.0, 1.0, 6)
        self._spin(form, "simulation.costs.slippage_ticks", 0, 100)
        self._double(form, "simulation.costs.tick_value_pct", 0.0, 10.0, 4)
        self._button(form, "Scan Available Complete Days", self._scan_complete_days)
        return widget

    def _data_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._line(form, "data.storage.type")
        self._line(form, "data.storage.path")
        self._line(form, "data.raw_output_dir")
        self._line(form, "data.report_output_dir")
        return widget

    def _schedule_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        self._check(form, "schedule.enabled")
        self._line(form, "schedule.timezone")
        self._line(form, "schedule.run_times", transform=lambda v: ", ".join(v or []))
        self._spin(form, "schedule.startup_delay_seconds", 0, 3600)
        self._check(form, "schedule.skip_if_running")
        self._line(form, "schedule.lock_file")
        self._line(form, "schedule.state_file")
        self._line(form, "schedule.log_dir")
        return widget

    def _line(self, form: QFormLayout, path: str, password: bool = False, transform=None) -> None:
        value = self._get(path, "")
        edit = QLineEdit(str(transform(value) if transform else value))
        if password:
            edit.setEchoMode(QLineEdit.Password)
        self.fields[path] = edit
        form.addRow(path, edit)

    def _check(self, form: QFormLayout, path: str) -> None:
        box = QCheckBox()
        box.setChecked(bool(self._get(path, False)))
        self.fields[path] = box
        form.addRow(path, box)

    def _spin(self, form: QFormLayout, path: str, minimum: int, maximum: int) -> None:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(int(self._get(path, minimum)))
        self.fields[path] = spin
        form.addRow(path, spin)

    def _double(self, form: QFormLayout, path: str, minimum: float, maximum: float, decimals: int) -> None:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(decimals)
        spin.setValue(float(self._get(path, minimum)))
        self.fields[path] = spin
        form.addRow(path, spin)

    def _combo(self, form: QFormLayout, path: str, values: list[str]) -> None:
        combo = QComboBox()
        combo.addItems(values)
        current = str(self._get(path, values[0]))
        if path == "app.mode" and current == "live":
            current = "kis_rest"
        if current in values:
            combo.setCurrentText(current)
        self.fields[path] = combo
        form.addRow(path, combo)

    def _button(self, form: QFormLayout, label: str, callback) -> None:
        button = QPushButton(label)
        button.clicked.connect(callback)
        row = QHBoxLayout()
        row.addWidget(button)
        wrapper = QWidget()
        wrapper.setLayout(row)
        form.addRow("", wrapper)

    def apply_to_values(self) -> None:
        for path, widget in self.fields.items():
            if isinstance(widget, QLineEdit):
                value: Any = widget.text()
                if path in {"market.nxt.signal_times", "schedule.run_times"}:
                    value = [item.strip() for item in value.split(",") if item.strip()]
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                value = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                value = widget.value()
            elif isinstance(widget, QComboBox):
                value = widget.currentText()
            else:
                continue
            self._set(path, value)
        self.status.append("Applied settings to memory.")

    def save(self) -> None:
        self.apply_to_values()
        path = self.config_path
        if path.name == "config.example.yaml":
            path = Path("config.yaml")
            self.config_path = path
        path.write_text(yaml.safe_dump(self.values, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.status.append(f"Saved {path}")
        self.accept()

    def _test_kis(self) -> None:
        self.apply_to_values()
        result = test_kis_rest(self.values)
        self.status.append(f"KIS REST {'OK' if result.ok else 'FAILED'}: {result.message}")

    def _test_telegram(self) -> None:
        self.apply_to_values()
        result = test_telegram(self.values)
        self.status.append(f"Telegram {'OK' if result.ok else 'FAILED'}: {result.message}")

    def _test_llm(self) -> None:
        self.apply_to_values()
        result = test_llm(self.values)
        self.status.append(f"LLM {'OK' if result.ok else 'FAILED'}: {result.message}")

    def _scan_complete_days(self) -> None:
        self.apply_to_values()
        store = SQLiteStore(self._get("data.storage.path", "data/market_data.sqlite3"))
        requested = int(self._get("simulation.date_selection.recent_complete_days", 30))
        selection = recent_complete_days(store, self.values, requested)
        if selection.selected_dates:
            msg = (
                f"Complete days available: {selection.complete_days_available}\n"
                f"Selected: {len(selection.selected_dates)} / {requested}\n"
                f"Range: {selection.selected_dates[0]} ~ {selection.selected_dates[-1]}"
            )
        else:
            msg = "No complete stored raw-data days found."
        self.status.append(msg)
        QMessageBox.information(self, "Complete Data Scan", msg)

    def _get(self, dotted_path: str, default=None):
        current: Any = self.values
        for part in dotted_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def _set(self, dotted_path: str, value: Any) -> None:
        current = self.values
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = value
