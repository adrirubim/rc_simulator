from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


@dataclass(frozen=True)
class Banner:
    widget: QWidget
    text: QLabel
    close_button: QPushButton


def build_banner(*, parent: QWidget, on_close: Callable[[], None]) -> Banner:
    banner = QWidget(parent)
    banner.setObjectName("banner")
    banner.setProperty("bannerKind", "muted")  # ok|warn|danger|muted

    layout = QHBoxLayout(banner)
    layout.setContentsMargins(10, 8, 10, 8)
    layout.setSpacing(10)

    text = QLabel("", banner)
    text.setWordWrap(True)
    layout.addWidget(text, 1)

    close = QPushButton("✕", banner)
    close.setObjectName("bannerClose")
    close.clicked.connect(on_close)
    close.setAccessibleName("Dismiss banner")
    close.setAccessibleDescription("Close and hide this notification banner")
    layout.addWidget(close, 0, alignment=Qt.AlignTop)

    banner.setVisible(False)
    return Banner(widget=banner, text=text, close_button=close)
