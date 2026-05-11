from __future__ import annotations

import sys
import traceback
from pathlib import Path

import yaml
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from kosim.config import AppConfig, load_config, load_example_config
from kosim.data.availability import recent_complete_days
from kosim.data.storage import SQLiteStore
from kosim.integration_tests import test_kis_rest, test_llm, test_telegram
from kosim.pipeline import DailyPipelineRunner, PipelineArtifacts
from kosim.scheduler import install_launchd, run_once as scheduler_run_once, scheduler_status, uninstall_launchd
from kosim.simulation.engine import RunEvent
from kosim.ui.progress_timeline import ProgressTimeline
from kosim.ui.run_status_panel import RunStatusPanel
from kosim.ui.settings_dialog import SettingsDialog


class PipelineWorker(QObject):
    event = Signal(object)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            runner = DailyPipelineRunner(self.config, emit=self.event.emit)
            artifacts = runner.run()
            self.completed.emit(artifacts)
        except Exception as exc:
            self.failed.emit(str(exc))


class IntegrationTestWorker(QObject):
    completed = Signal(object)

    def __init__(self, name: str, config: dict):
        super().__init__()
        self.name = name
        self.config = config

    def run(self) -> None:
        if self.name == "kis":
            self.completed.emit(test_kis_rest(self.config))
        elif self.name == "telegram":
            self.completed.emit(test_telegram(self.config))
        elif self.name == "llm":
            self.completed.emit(test_llm(self.config))


class SchedulerWorker(QObject):
    completed = Signal(object)

    def __init__(self, config_path: str, force: bool):
        super().__init__()
        self.config_path = config_path
        self.force = force

    def run(self) -> None:
        try:
            self.completed.emit(scheduler_run_once(self.config_path, force=self.force))
        except Exception as exc:
            exc.scheduler_traceback = traceback.format_exc()
            self.completed.emit(exc)


class ConditionsDialog(QDialog):
    HEADERS = ["Enabled", "LLM Queue", "Name", "Direction", "Min Count", "Threshold %", "Side", "Label", "Entry Time"]

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Condition Queue Settings")
        self.resize(1120, 620)
        self.config_path = Path(config.path)
        self.values = yaml.safe_load(yaml.safe_dump(config.values, allow_unicode=True)) or {}
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self._load_rows()

        add_button = QPushButton("Add")
        add_button.clicked.connect(self.add_row)
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self.delete_selected)
        defaults_button = QPushButton("Reset Defaults")
        defaults_button.clicked.connect(self.reset_defaults)

        toolbar = QHBoxLayout()
        toolbar.addWidget(add_button)
        toolbar.addWidget(delete_button)
        toolbar.addWidget(defaults_button)
        toolbar.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply_to_values)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.save)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.table, 1)
        layout.addWidget(buttons)

    def result_config(self) -> AppConfig:
        self.apply_to_values()
        return AppConfig(path=self.config_path, values=self.values)

    def _load_rows(self) -> None:
        self.table.setRowCount(0)
        cases = self.values.get("simulation", {}).get("strategy_conditions", [])
        for case in cases:
            self.add_row(case)
        self.table.resizeColumnsToContents()

    def add_row(self, case: dict | None = None) -> None:
        case = case or _default_condition_case(len(self._cases_from_table()) + 1)
        row = self.table.rowCount()
        self.table.insertRow(row)
        self._set_cell_widget(row, 0, _check_widget(bool(case.get("enabled", True))))
        self._set_cell_widget(row, 1, _check_widget(bool(case.get("llm_queue", True))))
        self.table.setItem(row, 2, QTableWidgetItem(str(case.get("name", "condition"))))
        direction = QComboBox()
        direction.addItems(["up", "down"])
        direction.setCurrentText(str(case.get("signal", {}).get("direction", "up")))
        self._set_cell_widget(row, 3, direction)
        min_count = QSpinBox()
        min_count.setRange(1, 30)
        min_count.setValue(int(case.get("signal", {}).get("min_count", 7)))
        self._set_cell_widget(row, 4, min_count)
        threshold = QDoubleSpinBox()
        threshold.setRange(0.0, 30.0)
        threshold.setDecimals(3)
        threshold.setValue(float(case.get("signal", {}).get("threshold_pct", 0.0)))
        self._set_cell_widget(row, 5, threshold)
        side = QComboBox()
        side.addItems(["long", "short"])
        side.setCurrentText(str(case.get("trade", {}).get("side", "long")))
        self._set_cell_widget(row, 6, side)
        self.table.setItem(row, 7, QTableWidgetItem(str(case.get("trade", {}).get("label", "long"))))
        self.table.setItem(row, 8, QTableWidgetItem(str(case.get("trade", {}).get("entry_time", "08:50"))))

    def delete_selected(self) -> None:
        for row in sorted({item.row() for item in self.table.selectedItems()}, reverse=True):
            self.table.removeRow(row)

    def reset_defaults(self) -> None:
        self.table.setRowCount(0)
        for count in [5, 7, 10]:
            self.add_row(_condition_case(f"top10_{count}_up_long", "up", count, "long", "long"))
        for count in [5, 7, 10]:
            self.add_row(_condition_case(f"top10_{count}_down_inverse", "down", count, "short", "inverse"))

    def apply_to_values(self) -> None:
        self.values.setdefault("simulation", {})["strategy_conditions"] = self._cases_from_table()

    def save(self) -> None:
        self.apply_to_values()
        path = self.config_path
        if path.name == "config.example.yaml":
            path = Path("config.yaml")
            self.config_path = path
        path.write_text(yaml.safe_dump(self.values, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.accept()

    def _cases_from_table(self) -> list[dict]:
        cases = []
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 2)
            label_item = self.table.item(row, 7)
            entry_item = self.table.item(row, 8)
            direction = self.table.cellWidget(row, 3)
            min_count = self.table.cellWidget(row, 4)
            threshold = self.table.cellWidget(row, 5)
            side = self.table.cellWidget(row, 6)
            name = _sanitize_condition_name(name_item.text() if name_item else f"condition_{row + 1}")
            label = label_item.text().strip() if label_item else side.currentText()
            cases.append(
                {
                    "name": name,
                    "enabled": _checked(self.table.cellWidget(row, 0)),
                    "llm_queue": _checked(self.table.cellWidget(row, 1)),
                    "rule": "min_positive_count",
                    "comparison": "greater_than",
                    "signal": {
                        "direction": direction.currentText(),
                        "threshold_pct": threshold.value(),
                        "min_count": min_count.value(),
                    },
                    "trade": {
                        "instrument": "kospi200_futures",
                        "side": side.currentText(),
                        "label": label,
                        "entry_time": entry_item.text().strip() if entry_item else "08:50",
                    },
                }
            )
        return cases

    def _set_cell_widget(self, row: int, column: int, widget: QWidget) -> None:
        self.table.setCellWidget(row, column, widget)


class MainWindow(QMainWindow):
    def __init__(self, config_path: str):
        super().__init__()
        self.setWindowTitle("KOSPI NXT Sweep Simulator")
        self.resize(1280, 820)
        self.config_path = config_path
        self.config = self._load_config()
        self.thread: QThread | None = None
        self.worker: PipelineWorker | None = None
        self.test_thread: QThread | None = None
        self.test_worker: IntegrationTestWorker | None = None
        self.scheduler_thread: QThread | None = None
        self.scheduler_worker: SchedulerWorker | None = None

        self.start_button = QPushButton("Run Sweep")
        self.start_button.clicked.connect(self.start_run)
        self.config_label = QLabel("")

        self.timeline = ProgressTimeline()
        self.status_panel = RunStatusPanel()
        self.log_panel = QTextEdit()
        self.log_panel.setReadOnly(True)
        self.result_table = QTableWidget(0, 9)
        self.result_table.setHorizontalHeaderLabels(
            ["Condition", "Signal", "Exit", "Trades", "Win Rate", "Loss Prob", "Avg %", "P05 %", "P95 %"]
        )
        self.report_viewer = QTextEdit()
        self.report_viewer.setReadOnly(True)

        self._build_layout()
        self._build_menu()
        self._load_config_label()

    def _build_layout(self) -> None:
        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.addWidget(self.start_button)
        top_layout.addWidget(self.config_label, 1)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Run Progress"))
        left_layout.addWidget(self.timeline, 2)
        left_layout.addWidget(QLabel("Current Status"))
        left_layout.addWidget(self.status_panel, 1)

        tabs = QTabWidget()
        tabs.addTab(self.result_table, "Results")
        tabs.addTab(self.report_viewer, "Markdown Report")
        tabs.addTab(self.log_panel, "Run Log")

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(tabs)
        splitter.setSizes([360, 900])

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(top)
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Open Config...", self.open_config)
        file_menu.addAction("Settings...", self.open_settings)
        file_menu.addAction("Save Config", self.save_config)
        file_menu.addAction("Save Config As...", self.save_config_as)
        file_menu.addAction("Reload Config", self.reload_config)

        mode_menu = self.menuBar().addMenu("Mode")
        self.mock_action = QAction("Mock Mode", self, checkable=True)
        self.kis_rest_action = QAction("KIS REST Mode", self, checkable=True)
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        mode_group.addAction(self.mock_action)
        mode_group.addAction(self.kis_rest_action)
        self.mock_action.triggered.connect(lambda: self.set_mode("mock"))
        self.kis_rest_action.triggered.connect(lambda: self.set_mode("kis_rest"))
        mode_menu.addAction(self.mock_action)
        mode_menu.addAction(self.kis_rest_action)
        self._sync_mode_actions()

        integrations_menu = self.menuBar().addMenu("Integrations")
        integrations_menu.addAction("Settings...", self.open_settings)
        integrations_menu.addAction("Test KIS REST API", lambda: self.start_integration_test("kis"))
        integrations_menu.addAction("Test Telegram", lambda: self.start_integration_test("telegram"))
        integrations_menu.addAction("Test LLM", lambda: self.start_integration_test("llm"))

        simulation_menu = self.menuBar().addMenu("Simulation")
        simulation_menu.addAction("Recent 10 Complete Data Days", lambda: self.apply_recent_complete_days(10))
        simulation_menu.addAction("Recent 20 Complete Data Days", lambda: self.apply_recent_complete_days(20))
        simulation_menu.addAction("Recent 30 Complete Data Days", lambda: self.apply_recent_complete_days(30))
        simulation_menu.addAction("Recent 60 Complete Data Days", lambda: self.apply_recent_complete_days(60))
        simulation_menu.addAction("Custom Complete Data Days...", self.edit_recent_complete_days)
        simulation_menu.addSeparator()
        simulation_menu.addAction("Run Sweep", self.start_run)

        conditions_menu = self.menuBar().addMenu("Conditions")
        conditions_menu.addAction("Open Condition Queue Settings...", self.open_conditions)
        conditions_menu.addSeparator()
        conditions_menu.addAction("Enable All Conditions", lambda: self.set_all_conditions("enabled", True))
        conditions_menu.addAction("Disable All Conditions", lambda: self.set_all_conditions("enabled", False))
        conditions_menu.addAction("Enable Long Conditions", self.enable_long_conditions)
        conditions_menu.addAction("Enable Inverse Conditions", self.enable_inverse_conditions)
        conditions_menu.addSeparator()
        conditions_menu.addAction("Enable All LLM Queue", lambda: self.set_all_conditions("llm_queue", True))
        conditions_menu.addAction("Disable All LLM Queue", lambda: self.set_all_conditions("llm_queue", False))
        conditions_menu.addSeparator()
        conditions_menu.addAction("Run Selected Conditions Now", self.start_run)

        schedule_menu = self.menuBar().addMenu("Schedule")
        self.schedule_enabled_action = QAction("Enable Scheduler", self, checkable=True)
        self.schedule_enabled_action.triggered.connect(self.set_scheduler_enabled)
        schedule_menu.addAction(self.schedule_enabled_action)
        schedule_menu.addSeparator()
        schedule_menu.addAction("Install macOS Schedule", self.install_scheduler)
        schedule_menu.addAction("Uninstall macOS Schedule", self.uninstall_scheduler)
        schedule_menu.addAction("Run Scheduled Job Now", self.run_scheduled_job_now)
        schedule_menu.addAction("View Scheduler Status", self.view_scheduler_status)
        schedule_menu.addAction("Open Scheduler Settings", self.open_settings)
        self._sync_schedule_action()

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("Current Status", lambda: self.open_text_file("Current_Status.md"))
        help_menu.addAction("Risk Review", lambda: self.open_text_file("docs/RISK_REVIEW.md"))
        help_menu.addAction("KIS Manual Notes", lambda: self.open_text_file("docs/KIS_MANUAL_NOTES.md"))

    def _load_config(self) -> AppConfig:
        if Path(self.config_path).exists():
            return load_config(self.config_path)
        return load_example_config()

    def _load_config_label(self) -> None:
        suffix = self.config_path if Path(self.config_path).exists() else "config.example.yaml (mock)"
        raw_mode = self.config.get("app.mode", "mock")
        mode = "KIS_REST" if raw_mode == "kis_rest" else "MOCK"
        selection = self.config.get("simulation.date_selection.mode", "date_range")
        scheduler_label = "ON" if bool(self.config.get("schedule.enabled", False)) else "OFF"
        self.config_label.setText(
            f"Config: {suffix}    Mode: {mode}    Date selection: {selection}    Scheduler: {scheduler_label}"
        )
        self._sync_mode_actions()
        self._sync_schedule_action()

    def start_run(self) -> None:
        self.start_button.setEnabled(False)
        self.thread = QThread()
        self.worker = PipelineWorker(self.config)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.event.connect(self.on_event)
        self.worker.completed.connect(self.on_completed)
        self.worker.failed.connect(self.on_failed)
        self.worker.completed.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self.start_button.setEnabled(True))
        self.thread.start()

    def on_event(self, event: RunEvent) -> None:
        self.timeline.apply_event(event)
        self.status_panel.apply_event(event)
        self.log_panel.append(f"[{event.status.upper()}] {event.step}: {event.message}")

    def on_completed(self, artifacts: PipelineArtifacts) -> None:
        metrics = artifacts.result.metrics[:100]
        self.result_table.setRowCount(len(metrics))
        for row_index, item in enumerate(metrics):
            values = [
                item.condition_name,
                item.signal_time,
                item.exit_time,
                str(item.trade_count),
                f"{item.win_rate:.1%}",
                f"{item.loss_probability:.1%}",
                f"{item.avg_return_pct:.3f}",
                f"{item.p05_return_pct:.3f}",
                f"{item.p95_return_pct:.3f}",
            ]
            for col_index, value in enumerate(values):
                self.result_table.setItem(row_index, col_index, QTableWidgetItem(value))
        self.result_table.resizeColumnsToContents()
        self.report_viewer.setPlainText(artifacts.simulation_report_path.read_text(encoding="utf-8"))

    def on_failed(self, message: str) -> None:
        self.log_panel.append(f"[FAILED] {message}")
        QMessageBox.critical(self, "Run failed", message)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self.config = dialog.result_config()
            self.config_path = str(self.config.path)
            self._load_config_label()
            self.log_panel.append("[CONFIG] Integrated settings applied")

    def open_conditions(self) -> None:
        dialog = ConditionsDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self.config = dialog.result_config()
            self.config_path = str(self.config.path)
            self._load_config_label()
            self.log_panel.append("[CONDITIONS] Condition queue settings applied")

    def set_all_conditions(self, key: str, value: bool) -> None:
        for condition in self.config.values.get("simulation", {}).get("strategy_conditions", []):
            condition[key] = value
        self._write_config(Path(self.config_path) if Path(self.config_path).exists() else Path("config.yaml"))
        self.log_panel.append(f"[CONDITIONS] Set {key}={value} for all conditions")

    def enable_long_conditions(self) -> None:
        for condition in self.config.values.get("simulation", {}).get("strategy_conditions", []):
            condition["enabled"] = condition.get("trade", {}).get("side") == "long"
        self._write_config(Path(self.config_path) if Path(self.config_path).exists() else Path("config.yaml"))
        self.log_panel.append("[CONDITIONS] Enabled long conditions only")

    def enable_inverse_conditions(self) -> None:
        for condition in self.config.values.get("simulation", {}).get("strategy_conditions", []):
            condition["enabled"] = condition.get("trade", {}).get("side") == "short"
        self._write_config(Path(self.config_path) if Path(self.config_path).exists() else Path("config.yaml"))
        self.log_panel.append("[CONDITIONS] Enabled inverse/short conditions only")

    def open_config(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open Config", str(Path.cwd()), "YAML Files (*.yaml *.yml)")
        if not path:
            return
        self.config_path = path
        self.config = load_config(path)
        self._load_config_label()
        self.log_panel.append(f"[CONFIG] Opened {path}")

    def save_config(self) -> None:
        path = Path(self.config_path)
        if path.name == "config.example.yaml" or not path.exists():
            path = Path("config.yaml")
            self.config_path = str(path)
            self.config = AppConfig(path=path, values=self.config.values)
        self._write_config(path)

    def save_config_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save Config As", "config.yaml", "YAML Files (*.yaml *.yml)")
        if not path:
            return
        self.config_path = path
        self.config = AppConfig(path=Path(path), values=self.config.values)
        self._write_config(Path(path))

    def reload_config(self) -> None:
        self.config = self._load_config()
        self._load_config_label()
        self.log_panel.append("[CONFIG] Reloaded")

    def _write_config(self, path: Path) -> None:
        if path.name == "config.example.yaml":
            QMessageBox.warning(self, "Blocked", "Do not overwrite config.example.yaml. Save to config.yaml instead.")
            return
        path.write_text(yaml.safe_dump(self.config.values, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self._load_config_label()
        self.log_panel.append(f"[CONFIG] Saved {path}")

    def set_mode(self, mode: str) -> None:
        self.config.values.setdefault("app", {})["mode"] = mode
        self._load_config_label()
        self.log_panel.append(f"[CONFIG] app.mode = {mode}")

    def set_scheduler_enabled(self, enabled: bool) -> None:
        self.config.values.setdefault("schedule", {})["enabled"] = enabled
        self._load_config_label()
        target = Path(self.config_path)
        if target.name == "config.example.yaml" or not target.exists():
            target = Path("config.yaml")
            self.config_path = str(target)
            self.config = AppConfig(path=target, values=self.config.values)
        self._write_config(target)
        self.log_panel.append(f"[SCHEDULE] schedule.enabled = {enabled}")

    def _sync_schedule_action(self) -> None:
        if hasattr(self, "schedule_enabled_action"):
            self.schedule_enabled_action.setChecked(bool(self.config.get("schedule.enabled", False)))

    def _sync_mode_actions(self) -> None:
        if not hasattr(self, "mock_action"):
            return
        mode = self.config.get("app.mode", "mock")
        is_kis_rest = mode == "kis_rest"
        self.mock_action.setChecked(not is_kis_rest)
        self.kis_rest_action.setChecked(is_kis_rest)

    def install_scheduler(self) -> None:
        try:
            plist_path = install_launchd(self.config_path)
        except Exception as exc:
            QMessageBox.critical(self, "Schedule install failed", str(exc))
            self.log_panel.append(f"[SCHEDULE:FAILED] install: {exc}")
            return
        self.log_panel.append(f"[SCHEDULE] Installed launchd plist: {plist_path}")
        QMessageBox.information(self, "Schedule installed", f"Installed launchd plist:\n{plist_path}")

    def uninstall_scheduler(self) -> None:
        try:
            plist_path = uninstall_launchd()
        except Exception as exc:
            QMessageBox.critical(self, "Schedule uninstall failed", str(exc))
            self.log_panel.append(f"[SCHEDULE:FAILED] uninstall: {exc}")
            return
        self.log_panel.append(f"[SCHEDULE] Uninstalled launchd plist: {plist_path}")
        QMessageBox.information(self, "Schedule uninstalled", f"Removed launchd plist:\n{plist_path}")

    def run_scheduled_job_now(self) -> None:
        if self.scheduler_thread is not None and self.scheduler_thread.isRunning():
            QMessageBox.information(self, "Scheduler already running", "A scheduled job is already running.")
            return
        self.scheduler_thread = QThread()
        self.scheduler_worker = SchedulerWorker(self.config_path, force=True)
        self.scheduler_worker.moveToThread(self.scheduler_thread)
        self.scheduler_thread.started.connect(self.scheduler_worker.run)
        self.scheduler_worker.completed.connect(self.on_scheduler_completed)
        self.scheduler_worker.completed.connect(self.scheduler_thread.quit)
        self.scheduler_thread.finished.connect(self.scheduler_worker.deleteLater)
        self.scheduler_thread.finished.connect(self.scheduler_thread.deleteLater)
        self.scheduler_thread.finished.connect(self._cleanup_scheduler_worker)
        self.log_panel.append("[SCHEDULE] Starting manual scheduled job with configured delay")
        self.scheduler_thread.start()

    def on_scheduler_completed(self, result) -> None:
        if isinstance(result, Exception):
            message = str(result)
            self.log_panel.append(f"[SCHEDULE:FAILED] {message}")
            QMessageBox.critical(self, "Scheduled job failed", message)
            return
        self.log_panel.append(f"[SCHEDULE:{result.status.upper()}] {result.message}")
        if result.report_path:
            self.log_panel.append(f"[SCHEDULE] Report: {result.report_path}")
        QMessageBox.information(self, f"Scheduled job {result.status}", result.message)

    def _cleanup_scheduler_worker(self) -> None:
        self.scheduler_worker = None
        self.scheduler_thread = None

    def view_scheduler_status(self) -> None:
        try:
            status = scheduler_status(self.config_path)
        except Exception as exc:
            QMessageBox.critical(self, "Scheduler status failed", str(exc))
            return
        state = status.get("state") or {}
        text = "\n".join(
            [
                f"enabled: {status.get('enabled')}",
                f"launchd_installed: {status.get('launchd_installed')}",
                f"run_times: {', '.join(status.get('run_times') or [])}",
                f"startup_delay_seconds: {status.get('startup_delay_seconds')}",
                f"state_file: {status.get('state_file')}",
                f"launchd_plist_path: {status.get('launchd_plist_path')}",
                f"last_status: {state.get('last_status')}",
                f"last_started_at: {state.get('last_started_at')}",
                f"last_finished_at: {state.get('last_finished_at')}",
                f"last_report: {state.get('last_report')}",
                f"last_error: {state.get('last_error')}",
            ]
        )
        self.report_viewer.setPlainText(text)
        QMessageBox.information(self, "Scheduler Status", text)

    def edit_top_n(self) -> None:
        current = int(self.config.get("market.universe.top_n", 10))
        value, ok = QInputDialog.getInt(self, "Universe Top N", "Top N", current, 1, 30)
        if ok:
            self.config.values["market"]["universe"]["top_n"] = value
            self.config.values["simulation"]["signal_condition"]["min_positive_count"] = value
            self._load_config_label()

    def edit_signal_times(self) -> None:
        current = ", ".join(self.config.get("market.nxt.signal_times", []))
        value, ok = QInputDialog.getText(self, "Signal Times", "Comma-separated HH:MM values", text=current)
        if ok:
            times = [item.strip() for item in value.split(",") if item.strip()]
            if times:
                self.config.values["market"]["nxt"]["signal_times"] = times

    def edit_exit_sweep(self) -> None:
        cfg = self.config.values["simulation"]["exit_sweep"]
        current = f"{cfg['start']}, {cfg['end']}, {cfg['interval_minutes']}"
        value, ok = QInputDialog.getText(self, "Exit Sweep", "start, end, interval_minutes", text=current)
        if not ok:
            return
        parts = [item.strip() for item in value.split(",")]
        if len(parts) != 3:
            QMessageBox.warning(self, "Invalid", "Use: 09:00, 15:20, 10")
            return
        cfg["start"], cfg["end"], cfg["interval_minutes"] = parts[0], parts[1], int(parts[2])

    def edit_costs(self) -> None:
        cfg = self.config.values["simulation"]["costs"]
        current = f"{cfg.get('fee_rate', 0.0)}, {cfg.get('slippage_ticks', 1)}, {cfg.get('tick_value_pct', 0.01)}"
        value, ok = QInputDialog.getText(self, "Costs", "fee_rate, slippage_ticks, tick_value_pct", text=current)
        if not ok:
            return
        parts = [item.strip() for item in value.split(",")]
        if len(parts) != 3:
            QMessageBox.warning(self, "Invalid", "Use: 0.0001, 1, 0.01")
            return
        cfg["fee_rate"], cfg["slippage_ticks"], cfg["tick_value_pct"] = float(parts[0]), int(parts[1]), float(parts[2])

    def edit_kis_settings(self) -> None:
        kis = self.config.values["kis"]
        self._edit_text_value(kis, "app_key", "KIS app_key")
        self._edit_text_value(kis, "app_secret", "KIS app_secret", password=True)
        self._edit_text_value(kis, "account_no", "KIS account_no")

    def edit_telegram_settings(self) -> None:
        tg = self.config.values["telegram"]
        enabled, ok = QInputDialog.getItem(self, "Telegram Enabled", "enabled", ["false", "true"], 1 if tg.get("enabled") else 0, False)
        if ok:
            tg["enabled"] = enabled == "true"
        self._edit_text_value(tg, "bot_token", "Telegram bot_token", password=True)
        self._edit_text_value(tg, "chat_id", "Telegram chat_id")

    def edit_llm_settings(self) -> None:
        llm = self.config.values["llm"]
        enabled, ok = QInputDialog.getItem(self, "LLM Enabled", "enabled", ["false", "true"], 1 if llm.get("enabled") else 0, False)
        if ok:
            llm["enabled"] = enabled == "true"
        for key in ["base_url", "model"]:
            self._edit_text_value(llm, key, f"LLM {key}")
        self._edit_text_value(llm, "api_key", "LLM api_key", password=True)

    def _edit_text_value(self, target: dict, key: str, title: str, password: bool = False) -> None:
        echo = QLineEdit.Password if password else QLineEdit.Normal
        value, ok = QInputDialog.getText(self, title, key, echo=echo, text=str(target.get(key, "")))
        if ok:
            target[key] = value

    def edit_date_range(self) -> None:
        cfg = self.config.values["simulation"]
        current = f"{cfg['date_range']['start']}, {cfg['date_range']['end']}"
        value, ok = QInputDialog.getText(self, "Date Range Mode", "start, end", text=current)
        if not ok:
            return
        parts = [item.strip() for item in value.split(",")]
        if len(parts) != 2:
            QMessageBox.warning(self, "Invalid", "Use: 2026-04-01, 2026-05-07")
            return
        cfg.setdefault("date_selection", {})["mode"] = "date_range"
        cfg["date_range"]["start"], cfg["date_range"]["end"] = parts[0], parts[1]
        self._load_config_label()

    def edit_recent_complete_days(self) -> None:
        current = int(self.config.get("simulation.date_selection.recent_complete_days", 30))
        value, ok = QInputDialog.getInt(self, "Recent Complete Data Days", "Days", current, 1, 1000)
        if ok:
            self.apply_recent_complete_days(value)

    def apply_recent_complete_days(self, days: int) -> None:
        self.config.values["simulation"].setdefault("date_selection", {})["mode"] = "recent_complete_data_days"
        self.config.values["simulation"]["date_selection"]["recent_complete_days"] = days
        store = SQLiteStore(self.config.get("data.storage.path", "data/market_data.sqlite3"))
        selection = recent_complete_days(store, self.config.values, days)
        msg = (
            f"Requested: {days}\n"
            f"Complete days available: {selection.complete_days_available}\n"
            f"Selected: {len(selection.selected_dates)}\n"
        )
        if selection.selected_dates:
            msg += f"Selected range: {selection.selected_dates[0]} ~ {selection.selected_dates[-1]}"
        else:
            msg += "No complete stored raw-data days found."
        QMessageBox.information(self, "Recent Complete Data Days", msg)
        self._load_config_label()

    def start_integration_test(self, name: str) -> None:
        if self.test_thread is not None and self.test_thread.isRunning():
            QMessageBox.information(self, "Test already running", "An integration test is already running. Please wait for it to finish.")
            return
        self.test_thread = QThread()
        self.test_worker = IntegrationTestWorker(name, self.config.values)
        self.test_worker.moveToThread(self.test_thread)
        self.test_thread.started.connect(self.test_worker.run)
        self.test_worker.completed.connect(self.on_integration_test_completed)
        self.test_worker.completed.connect(self.test_thread.quit)
        self.test_thread.finished.connect(self.test_worker.deleteLater)
        self.test_thread.finished.connect(self.test_thread.deleteLater)
        self.test_thread.finished.connect(self._cleanup_integration_test)
        self.log_panel.append(f"[TEST] Starting {name}")
        self.test_thread.start()

    def on_integration_test_completed(self, result) -> None:
        status = "OK" if result.ok else "FAILED"
        self.log_panel.append(f"[TEST:{status}] {result.name}: {result.message}")
        QMessageBox.information(self, f"{result.name} Test {status}", result.message)

    def _cleanup_integration_test(self) -> None:
        self.test_worker = None
        self.test_thread = None

    def open_text_file(self, path: str) -> None:
        file_path = Path(path)
        if not file_path.exists():
            QMessageBox.warning(self, "Missing", f"{path} not found")
            return
        self.report_viewer.setPlainText(file_path.read_text(encoding="utf-8"))

    def closeEvent(self, event) -> None:
        running_threads = []
        if self.thread is not None and self.thread.isRunning():
            running_threads.append("simulation")
        if self.test_thread is not None and self.test_thread.isRunning():
            running_threads.append("integration test")
        if self.scheduler_thread is not None and self.scheduler_thread.isRunning():
            running_threads.append("scheduled job")
        if running_threads:
            QMessageBox.warning(
                self,
                "Still running",
                f"Cannot close while {', '.join(running_threads)} is running. Please wait for completion.",
            )
            event.ignore()
            return
        event.accept()


def launch(config_path: str = "config.yaml") -> int:
    app = QApplication(sys.argv)
    window = MainWindow(config_path)
    window.show()
    return app.exec()


def _check_widget(checked: bool) -> QCheckBox:
    box = QCheckBox()
    box.setChecked(checked)
    return box


def _checked(widget) -> bool:
    return bool(widget.isChecked()) if isinstance(widget, QCheckBox) else False


def _default_condition_case(index: int) -> dict:
    return _condition_case(f"condition_{index}", "up", 7, "long", "long")


def _condition_case(name: str, direction: str, min_count: int, side: str, label: str) -> dict:
    return {
        "name": _sanitize_condition_name(name),
        "enabled": True,
        "llm_queue": True,
        "rule": "min_positive_count",
        "comparison": "greater_than",
        "signal": {"direction": direction, "threshold_pct": 0.0, "min_count": min_count},
        "trade": {"instrument": "kospi200_futures", "side": side, "label": label, "entry_time": "08:50"},
    }


def _sanitize_condition_name(value: str) -> str:
    text = str(value or "condition").lower()
    chars = [char if char.isalnum() else "_" for char in text]
    return "_".join("".join(chars).split("_")) or "condition"
