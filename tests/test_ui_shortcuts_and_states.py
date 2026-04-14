from __future__ import annotations

import queue
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class _MemSettings:
    store: dict[str, Any] = field(default_factory=dict)

    def value(self, key: str, defaultValue: Any | None = None) -> Any:
        return self.store.get(key, defaultValue)

    def setValue(self, key: str, value: Any) -> None:
        self.store[key] = value


@dataclass
class _StubController:
    events: queue.Queue = field(default_factory=queue.Queue)
    scan_thread: Any = None
    drive_thread: Any = None
    stop_event: Any = None

    def start_scan(self) -> bool:  # pragma: no cover
        return True

    def cancel_scan(self) -> bool:  # pragma: no cover
        return True

    def connect(self, _car) -> bool:  # pragma: no cover
        return False

    def disconnect(self) -> None:  # pragma: no cover
        return None

    def shutdown(self) -> None:  # pragma: no cover
        return None


def _ensure_qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_scan_button_shows_cancel_when_scanning(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    monkeypatch.setenv("RC_UI_START_LAYOUT", "A")

    app = _ensure_qt_app()

    from rc_simulator.ui_qt.strings import UI
    from rc_simulator.ui_qt.views.main_window import MainWindow

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()

    w.is_scanning = True
    w._update_controls()  # type: ignore[attr-defined]
    app.processEvents()

    assert w.btn_scan.isVisible()
    assert w.btn_scan.isEnabled()
    assert w.btn_scan.text() == UI.scan_button_cancel


def test_enter_triggers_connect_when_not_typing(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    monkeypatch.setenv("RC_UI_START_LAYOUT", "A")

    app = _ensure_qt_app()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    from rc_simulator.ui_qt.views.main_window import MainWindow

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()

    called = {"ok": False}

    def _fake_connect_selected() -> None:
        called["ok"] = True

    w.connect_selected = _fake_connect_selected  # type: ignore[method-assign]

    w.list.setFocus()
    app.processEvents()

    ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key_Return, Qt.NoModifier)
    w.keyPressEvent(ev)
    assert called["ok"] is True


@pytest.mark.parametrize(
    ("layout_id", "drive_text", "panels_text"),
    [
        ("A", "Drive", "Panels"),
        ("C", "Drive", "Dashboard"),
        ("B", "Dashboard", "Panels"),
    ],
)
def test_header_nav_buttons_show_destination(layout_id: str, drive_text: str, panels_text: str, monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    monkeypatch.setenv("RC_UI_START_LAYOUT", "A")

    app = _ensure_qt_app()

    from rc_simulator.ui_qt.views.main_window import MainWindow

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()

    w._apply_layout_now(layout_id)  # type: ignore[attr-defined]
    app.processEvents()

    assert w.btn_drive.text() == drive_text
    assert w.btn_debug.text() == panels_text


def test_drive_guard_overlay_visible_when_not_connected(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    monkeypatch.setenv("RC_UI_START_LAYOUT", "A")

    app = _ensure_qt_app()

    from rc_simulator.ui_qt.views.main_window import MainWindow

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()

    w.is_connected = False
    w._apply_layout_now("B")  # type: ignore[attr-defined]
    app.processEvents()

    assert w.drive_guard_overlay.isVisible()
