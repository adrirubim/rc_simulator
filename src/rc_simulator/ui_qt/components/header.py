from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

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
    badge_time: QLabel
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

    # Three-zone header: left (identity), center (instruments), right (actions).
    left = QWidget(header_widget)
    left_l = QHBoxLayout(left)
    left_l.setContentsMargins(12, 8, 8, 8)
    left_l.setSpacing(10)

    center = QWidget(header_widget)
    center_l = QHBoxLayout(center)
    center_l.setContentsMargins(8, 8, 8, 8)
    center_l.setSpacing(8)
    center.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)

    right = QWidget(header_widget)
    right_l = QHBoxLayout(right)
    right_l.setContentsMargins(8, 8, 12, 8)
    right_l.setSpacing(8)

    title = QLabel(UI.app_title, left)
    title.setObjectName("title")
    left_l.addWidget(title)

    header_l.addWidget(left, 0, Qt.AlignmentFlag.AlignVCenter)
    header_l.addStretch(1)
    header_l.addWidget(center, 0, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
    header_l.addStretch(1)
    header_l.addWidget(right, 0, Qt.AlignmentFlag.AlignVCenter)

    # Single state badge: we keep `badge_scan` for backward compatibility but hide it.
    badge_scan = QLabel(UI.badge_scanning, header_widget)
    badge_scan.setProperty("badge", True)
    badge_scan.setProperty("badgeKind", "warn")
    badge_scan.setVisible(False)
    # Do not add to layout (single-badge header).

    badge_conn = QLabel(UI.badge_disconnected, center)
    badge_moza = QLabel(UI.badge_moza_unknown, center)
    badge_video = QLabel(UI.badge_video_off, center)
    badge_output = QLabel("+0.000", center)
    badge_time = QLabel(UI.badge_time_placeholder, center)
    for b in (badge_conn, badge_moza, badge_video, badge_output, badge_time):
        b.setProperty("badge", True)
        b.setProperty("badgeKind", "muted")
        b.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        center_l.addWidget(b)
    badge_output.setProperty("mono", True)
    badge_time.setProperty("mono", True)

    btn_drive = QPushButton(UI.drive_button, right)
    btn_drive.setCheckable(True)
    btn_drive.clicked.connect(on_toggle_drive_mode)
    btn_drive.setToolTip(UI.drive_tooltip)
    btn_drive.setAccessibleName("Drive mode")
    btn_drive.setAccessibleDescription("Toggle Drive mode layout")
    right_l.addWidget(btn_drive)

    btn_debug = QPushButton(UI.panels_button, right)
    btn_debug.setCheckable(True)
    btn_debug.clicked.connect(on_toggle_debug_mode)
    btn_debug.setToolTip(UI.panels_tooltip)
    btn_debug.setAccessibleName("Panels")
    btn_debug.setAccessibleDescription("Toggle Panels layout")
    right_l.addWidget(btn_debug)

    btn_settings = QPushButton(UI.settings_button, right)
    btn_settings.setCheckable(True)
    btn_settings.clicked.connect(on_toggle_settings_mode)
    btn_settings.setToolTip(UI.settings_tooltip)
    btn_settings.setAccessibleName("Settings")
    btn_settings.setAccessibleDescription("Toggle Settings layout")
    right_l.addWidget(btn_settings)

    btn_min = QPushButton(UI.window_minimize_glyph, right)
    btn_min.setObjectName("windowMin")
    btn_min.clicked.connect(on_minimize)
    btn_min.setAccessibleName("Minimize window")
    btn_min.setAccessibleDescription("Minimize the application window")
    right_l.addWidget(btn_min)

    btn_max = QPushButton(UI.window_maximize_glyph, right)
    btn_max.setObjectName("windowMax")
    btn_max.clicked.connect(on_maximize_restore)
    btn_max.setAccessibleName("Maximize or restore window")
    btn_max.setAccessibleDescription("Toggle between maximized and normal window size")
    right_l.addWidget(btn_max)

    btn_close = QPushButton(UI.window_close_glyph, right)
    btn_close.setObjectName("windowClose")
    btn_close.clicked.connect(on_close)
    btn_close.setAccessibleName("Close window")
    btn_close.setAccessibleDescription("Close the application")
    right_l.addWidget(btn_close)

    return Header(
        widget=header_widget,
        title=title,
        badge_scan=badge_scan,
        badge_conn=badge_conn,
        badge_moza=badge_moza,
        badge_video=badge_video,
        badge_output=badge_output,
        badge_time=badge_time,
        btn_drive=btn_drive,
        btn_debug=btn_debug,
        btn_settings=btn_settings,
        btn_min=btn_min,
        btn_max=btn_max,
        btn_close=btn_close,
    )
