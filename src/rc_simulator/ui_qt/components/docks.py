from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..strings import UI


@dataclass(frozen=True)
class LogDock:
    dock: QDockWidget
    filter: QLineEdit
    view: QPlainTextEdit
    pause_button: QPushButton
    clear_button: QPushButton


@dataclass(frozen=True)
class LogPanel:
    widget: QWidget
    filter: QLineEdit
    view: QPlainTextEdit
    pause_button: QPushButton
    clear_button: QPushButton


def build_log_panel(
    *,
    parent: QWidget,
    on_filter_changed: Callable[[], None],
    on_pause_toggled: Callable[[bool], None],
    on_clear_clicked: Callable[[], None],
) -> LogPanel:
    wrap = QWidget(parent)
    wrap.setObjectName("systemLogPanel")
    panel_l = QVBoxLayout(wrap)
    panel_l.setContentsMargins(0, 0, 0, 0)
    panel_l.setSpacing(8)

    title = QLabel(UI.log_dock_title, wrap)
    title.setObjectName("title")
    panel_l.addWidget(title)

    filter_edit = QLineEdit(wrap)
    filter_edit.setPlaceholderText(UI.log_filter_placeholder)
    filter_edit.textChanged.connect(lambda _t: on_filter_changed())
    panel_l.addWidget(filter_edit)

    view = QPlainTextEdit(wrap)
    view.setObjectName("logView")
    view.setReadOnly(True)
    view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    panel_l.addWidget(view, 1)

    log_btns = QWidget(wrap)
    log_btns_l = QHBoxLayout(log_btns)
    log_btns_l.setContentsMargins(0, 0, 0, 0)

    pause_btn = QPushButton(UI.log_pause, log_btns)
    pause_btn.setCheckable(True)
    pause_btn.toggled.connect(on_pause_toggled)
    pause_btn.setToolTip(UI.log_pause_tooltip)

    clear_btn = QPushButton(UI.log_clear, log_btns)
    clear_btn.clicked.connect(on_clear_clicked)
    clear_btn.setToolTip(UI.log_clear_tooltip)

    log_btns_l.addWidget(pause_btn)
    log_btns_l.addWidget(clear_btn)
    panel_l.addWidget(log_btns)

    return LogPanel(widget=wrap, filter=filter_edit, view=view, pause_button=pause_btn, clear_button=clear_btn)


@dataclass(frozen=True)
class DebugDocks:
    telemetry_dock: QDockWidget
    trace_dock: QDockWidget
    t_out: QLabel
    steer_bar: QProgressBar
    gas_bar: QProgressBar
    brake_bar: QProgressBar
    telemetry_raw: QTextEdit
    trace_view: QTextEdit


def build_log_dock(
    *,
    main_window: QMainWindow,
    on_filter_changed: Callable[[], None],
    on_pause_toggled: Callable[[bool], None],
    on_clear_clicked: Callable[[], None],
) -> LogDock:
    dock = QDockWidget(UI.log_dock_title, main_window)
    dock.setObjectName("log_dock")
    dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)

    panel = build_log_panel(
        parent=dock,
        on_filter_changed=on_filter_changed,
        on_pause_toggled=on_pause_toggled,
        on_clear_clicked=on_clear_clicked,
    )
    dock_body = panel.widget
    dock_l = dock_body.layout()
    if isinstance(dock_l, QVBoxLayout):
        dock_l.setContentsMargins(8, 8, 8, 8)
    dock.setWidget(dock_body)
    main_window.addDockWidget(Qt.RightDockWidgetArea, dock)

    return LogDock(
        dock=dock,
        filter=panel.filter,
        view=panel.view,
        pause_button=panel.pause_button,
        clear_button=panel.clear_button,
    )


def build_debug_docks(*, main_window: QMainWindow) -> DebugDocks:
    telemetry_dock = QDockWidget(UI.debug_telemetry_dock_title, main_window)
    telemetry_dock.setObjectName("telemetry_dock")
    telemetry_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)

    t_body = QWidget(telemetry_dock)
    t_l = QVBoxLayout(t_body)
    t_l.setContentsMargins(8, 8, 8, 8)
    t_l.setSpacing(8)

    t_out = QLabel(UI.debug_output_label.format(value="+0.000"), t_body)
    t_out.setProperty("label", True)
    t_l.addWidget(t_out)

    def _make_bar(label: str) -> tuple[QLabel, QProgressBar]:
        wrap = QWidget(t_body)
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(4)
        lab = QLabel(label, wrap)
        lab.setProperty("label", True)
        bar = QProgressBar(wrap)
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        wl.addWidget(lab)
        wl.addWidget(bar)
        t_l.addWidget(wrap)
        return lab, bar

    _steer_lab, steer_bar = _make_bar(UI.debug_steering_label)
    _gas_lab, gas_bar = _make_bar(UI.debug_throttle_label)
    _brake_lab, brake_bar = _make_bar(UI.debug_brake_label)
    steer_bar.setProperty("barKind", "steer")
    gas_bar.setProperty("barKind", "gas")
    brake_bar.setProperty("barKind", "brake")

    telemetry_raw = QTextEdit(t_body)
    telemetry_raw.setReadOnly(True)
    telemetry_raw.setMinimumHeight(160)
    t_l.addWidget(telemetry_raw, 1)

    telemetry_dock.setWidget(t_body)
    main_window.addDockWidget(Qt.BottomDockWidgetArea, telemetry_dock)

    trace_dock = QDockWidget(UI.debug_trace_dock_title, main_window)
    trace_dock.setObjectName("trace_dock")
    trace_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

    tr_body = QWidget(trace_dock)
    tr_l = QVBoxLayout(tr_body)
    tr_l.setContentsMargins(8, 8, 8, 8)

    trace_view = QTextEdit(tr_body)
    trace_view.setReadOnly(True)
    tr_l.addWidget(trace_view, 1)

    trace_dock.setWidget(tr_body)
    main_window.addDockWidget(Qt.BottomDockWidgetArea, trace_dock)

    telemetry_dock.hide()
    trace_dock.hide()

    return DebugDocks(
        telemetry_dock=telemetry_dock,
        trace_dock=trace_dock,
        t_out=t_out,
        steer_bar=steer_bar,
        gas_bar=gas_bar,
        brake_bar=brake_bar,
        telemetry_raw=telemetry_raw,
        trace_view=trace_view,
    )
