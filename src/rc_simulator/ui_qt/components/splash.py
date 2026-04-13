from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QFont, QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget


class SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setObjectName("splash")
        self.setFixedSize(520, 260)

        root = QWidget(self)
        root.setObjectName("splashRoot")

        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        title = QLabel("RC simulator", root)
        title.setObjectName("splashTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        f = QFont("Segoe UI", 28)
        f.setWeight(QFont.Weight.DemiBold)
        title.setFont(f)

        bar = QProgressBar(root)
        bar.setObjectName("splashProgress")
        bar.setRange(0, 0)  # indeterminate
        bar.setTextVisible(False)
        bar.setFixedHeight(10)

        layout.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(bar)
        layout.addStretch(2)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

    def center_on_screen(self) -> None:
        # Center on the "active" monitor (best effort):
        # 1) screen of the currently focused/active window (most reliable)
        # 2) screen under the cursor
        # 3) primary screen fallback
        win = QGuiApplication.focusWindow()
        if win is None:
            active = QApplication.activeWindow()
            win = active.windowHandle() if active is not None else None

        screen = (win.screen() if win is not None else None) or QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        g = screen.availableGeometry()
        w = self.width()
        h = self.height()
        x = int(g.x() + (g.width() - w) / 2)
        y = int(g.y() + (g.height() - h) / 2)
        self.move(x, y)
