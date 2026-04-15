from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor, QFont, QGuiApplication
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QVBoxLayout, QWidget

from ..strings import UI


class SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setObjectName("splash")
        self.setFixedSize(560, 280)

        root = QWidget(self)
        root.setObjectName("splashRoot")

        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        title = QLabel(UI.app_title, root)
        title.setObjectName("splashTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        f = QFont("Segoe UI", 36)
        f.setWeight(QFont.Weight.Bold)
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

        self._did_bind_screen_changed = False
        self._lock_center_until_s: float = 0.0
        self._recentering: bool = False
        self._center_lock_timer: QTimer | None = None

    def showEvent(self, event) -> None:
        # Best practice: center using the *actual screen of this window* (windowHandle().screen()).
        # On some platforms (incl. WSLg), the window handle/screen is only available after show.
        if not self._did_bind_screen_changed:
            self._did_bind_screen_changed = True

            def _bind() -> None:
                try:
                    wh = self.windowHandle()
                    if wh is None:
                        return
                    # Recenter if the compositor moves the splash to another monitor.
                    wh.screenChanged.connect(lambda _s: self.center_on_screen())  # type: ignore[attr-defined]
                except Exception:
                    pass

            QTimer.singleShot(0, _bind)

        # Re-center a few times to win over early configure events.
        for delay_ms in (0, 16, 50, 150, 300):
            QTimer.singleShot(delay_ms, self.center_on_screen)

        # Hard lock centering briefly: if the compositor moves the splash right after mapping,
        # re-center deterministically for a short window, then stop (avoid infinite "WM fights").
        self._lock_center_until_s = time.monotonic() + 0.7
        if self._center_lock_timer is None:
            self._center_lock_timer = QTimer(self)
            self._center_lock_timer.setInterval(16)
            self._center_lock_timer.timeout.connect(self._tick_center_lock)
        self._center_lock_timer.start()
        super().showEvent(event)

    def _tick_center_lock(self) -> None:
        if time.monotonic() >= self._lock_center_until_s:
            if self._center_lock_timer is not None:
                self._center_lock_timer.stop()
            return
        self.center_on_screen()

    def moveEvent(self, event) -> None:
        # If the WM nudges the splash during the lock window, snap back to center.
        if time.monotonic() < self._lock_center_until_s:
            self.center_on_screen()
        super().moveEvent(event)

    def center_on_screen(self) -> None:
        # Center on the most correct screen:
        # 1) screen of THIS splash window handle (ground truth)
        # 2) screen under the cursor (startup heuristic)
        # 3) focused/active window screen fallback
        # 4) primary screen fallback
        screen = None
        try:
            wh = self.windowHandle()
            screen = wh.screen() if wh is not None else None
        except Exception:
            screen = None
        if screen is None:
            screen = QGuiApplication.screenAt(QCursor.pos())
        if screen is None:
            win = QGuiApplication.focusWindow()
            if win is None:
                active = QApplication.activeWindow()
                win = active.windowHandle() if active is not None else None
            screen = win.screen() if win is not None else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        # Use full screen geometry (not availableGeometry) to center visually on the monitor.
        # Also center using frameGeometry to avoid compositor/shadow offsets.
        if self._recentering:
            return
        self._recentering = True
        try:
            g = screen.geometry()
            fg = self.frameGeometry()
            fg.moveCenter(g.center())
            self.move(fg.topLeft())
        finally:
            self._recentering = False
