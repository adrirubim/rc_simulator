from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


@dataclass(frozen=True)
class Header:
    widget: QWidget
    title: QLabel
    badge_scan: QLabel
    badge_conn: QLabel
    badge_moza: QLabel
    badge_video: QLabel
    badge_output: QLabel
    btn_drive: QPushButton
    btn_debug: QPushButton


def build_header(
    *,
    parent: QWidget,
    on_toggle_drive_mode: Callable[[], None],
    on_toggle_debug_mode: Callable[[], None],
) -> Header:
    header_widget = QWidget(parent)
    header_l = QHBoxLayout(header_widget)
    header_l.setContentsMargins(0, 0, 0, 0)
    header_l.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    title = QLabel("RC Simulator", header_widget)
    title.setObjectName("title")
    header_l.addWidget(title)

    header_l.addStretch(1)

    badge_scan = QLabel("SCANSIONE", header_widget)
    badge_scan.setProperty("badge", True)
    badge_scan.setProperty("badgeKind", "warn")
    badge_scan.setVisible(False)
    header_l.addWidget(badge_scan)

    badge_conn = QLabel("DISCONNESSO", header_widget)
    badge_moza = QLabel("MOZA: --", header_widget)
    badge_video = QLabel("VIDEO OFF", header_widget)
    badge_output = QLabel("+0.000", header_widget)
    for b in (badge_conn, badge_moza, badge_video, badge_output):
        b.setProperty("badge", True)
        b.setProperty("badgeKind", "muted")
        header_l.addWidget(b)

    btn_drive = QPushButton("Guida", header_widget)
    btn_drive.setCheckable(True)
    btn_drive.clicked.connect(on_toggle_drive_mode)
    btn_drive.setToolTip("Modalità Guida (schermo intero). Esc per uscire dalla modalità Guida.")
    header_l.addWidget(btn_drive)

    btn_debug = QPushButton("Debug", header_widget)
    btn_debug.setCheckable(True)
    btn_debug.clicked.connect(on_toggle_debug_mode)
    btn_debug.setToolTip("Telemetria/Trace dockabili (layout C).")
    header_l.addWidget(btn_debug)

    return Header(
        widget=header_widget,
        title=title,
        badge_scan=badge_scan,
        badge_conn=badge_conn,
        badge_moza=badge_moza,
        badge_video=badge_video,
        badge_output=badge_output,
        btn_drive=btn_drive,
        btn_debug=btn_debug,
    )
