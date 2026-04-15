from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..strings import UI


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
    btn_settings: QPushButton
    btn_min: QPushButton
    btn_max: QPushButton
    btn_close: QPushButton


def build_header(
    *,
    parent: QWidget,
    on_toggle_drive_mode: Callable[[], None],
    on_toggle_debug_mode: Callable[[], None],
    on_toggle_settings_mode: Callable[[], None],
    on_minimize: Callable[[], None],
    on_maximize_restore: Callable[[], None],
    on_close: Callable[[], None],
    on_start_move: Callable[[], None],
) -> Header:
    class TitleBar(QWidget):
        def mousePressEvent(self, event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                on_start_move()
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseDoubleClickEvent(self, event) -> None:
            if event.button() == Qt.MouseButton.LeftButton:
                on_maximize_restore()
                event.accept()
                return
            super().mouseDoubleClickEvent(event)

    header_widget = TitleBar(parent)
    header_widget.setObjectName("titleBar")
    header_l = QHBoxLayout(header_widget)
    header_l.setContentsMargins(0, 0, 0, 0)
    header_l.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    title = QLabel(UI.app_title, header_widget)
    title.setObjectName("title")
    header_l.addWidget(title)

    header_l.addStretch(1)

    # Single state badge: we keep `badge_scan` for backward compatibility but hide it.
    badge_scan = QLabel(UI.badge_scanning, header_widget)
    badge_scan.setProperty("badge", True)
    badge_scan.setProperty("badgeKind", "warn")
    badge_scan.setVisible(False)
    # Do not add to layout (single-badge header).

    badge_conn = QLabel(UI.badge_disconnected, header_widget)
    badge_moza = QLabel(UI.badge_moza_unknown, header_widget)
    badge_video = QLabel(UI.badge_video_off, header_widget)
    badge_output = QLabel("+0.000", header_widget)
    for b in (badge_conn, badge_moza, badge_video, badge_output):
        b.setProperty("badge", True)
        b.setProperty("badgeKind", "muted")
        header_l.addWidget(b)
    badge_output.setProperty("mono", True)

    btn_drive = QPushButton(UI.drive_button, header_widget)
    btn_drive.setCheckable(True)
    btn_drive.clicked.connect(on_toggle_drive_mode)
    btn_drive.setToolTip(UI.drive_tooltip)
    btn_drive.setAccessibleName("Drive mode")
    btn_drive.setAccessibleDescription("Toggle Drive mode layout")
    header_l.addWidget(btn_drive)

    btn_debug = QPushButton(UI.panels_button, header_widget)
    btn_debug.setCheckable(True)
    btn_debug.clicked.connect(on_toggle_debug_mode)
    btn_debug.setToolTip(UI.panels_tooltip)
    btn_debug.setAccessibleName("Panels")
    btn_debug.setAccessibleDescription("Toggle Panels layout")
    header_l.addWidget(btn_debug)

    btn_settings = QPushButton(UI.settings_button, header_widget)
    btn_settings.setCheckable(True)
    btn_settings.clicked.connect(on_toggle_settings_mode)
    btn_settings.setToolTip(UI.settings_tooltip)
    btn_settings.setAccessibleName("Settings")
    btn_settings.setAccessibleDescription("Toggle Settings layout")
    header_l.addWidget(btn_settings)

    btn_min = QPushButton("–", header_widget)
    btn_min.setObjectName("windowMin")
    btn_min.clicked.connect(on_minimize)
    btn_min.setAccessibleName("Minimize window")
    btn_min.setAccessibleDescription("Minimize the application window")
    header_l.addWidget(btn_min)

    btn_max = QPushButton("□", header_widget)
    btn_max.setObjectName("windowMax")
    btn_max.clicked.connect(on_maximize_restore)
    btn_max.setAccessibleName("Maximize or restore window")
    btn_max.setAccessibleDescription("Toggle between maximized and normal window size")
    header_l.addWidget(btn_max)

    btn_close = QPushButton("✕", header_widget)
    btn_close.setObjectName("windowClose")
    btn_close.clicked.connect(on_close)
    btn_close.setAccessibleName("Close window")
    btn_close.setAccessibleDescription("Close the application")
    header_l.addWidget(btn_close)

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
        btn_settings=btn_settings,
        btn_min=btn_min,
        btn_max=btn_max,
        btn_close=btn_close,
    )
