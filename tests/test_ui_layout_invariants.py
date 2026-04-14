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
        return False

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


@pytest.mark.parametrize("layout_id", ["A", "B", "C"])
def test_layout_invariants(layout_id: str, monkeypatch) -> None:
    # Keep tests deterministic and avoid background threads / network.
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("RC_UI_AUTO_SCAN", "0")
    monkeypatch.setenv("RC_UI_DEFAULT_LAYOUT", "A")
    # Ensure the startup layout applied in showEvent matches the test case.
    monkeypatch.setenv("RC_UI_START_LAYOUT", layout_id)

    app = _ensure_qt_app()

    from rc_simulator.ui_qt.views.main_window import MainWindow

    w = MainWindow(settings=_MemSettings(), controller=_StubController())
    w.show()
    app.processEvents()
    # Re-impose deterministically (avoid fade/timers in apply_layout()).
    w._apply_layout_now(layout_id)  # type: ignore[attr-defined]
    app.processEvents()

    if layout_id == "B":
        assert not w.header_widget.isVisible()
        assert not w.left_panel.isVisible()
        assert not w.bottom.isVisible()
        assert not w.log_dock.isVisible()
        assert not w.telemetry_dock.isVisible()
        assert not w.trace_dock.isVisible()
        assert w.hud.isVisible()
    elif layout_id == "C":
        assert w.header_widget.isVisible()
        assert w.left_panel.isVisible()
        assert w.bottom.isVisible()
        assert w.log_dock.isVisible()
        assert w.telemetry_dock.isVisible()
        assert w.trace_dock.isVisible()
        assert not w.hud.isVisible()
    else:
        assert w.header_widget.isVisible()
        assert w.left_panel.isVisible()
        assert w.bottom.isVisible()
        assert w.log_dock.isVisible()
        assert not w.telemetry_dock.isVisible()
        assert not w.trace_dock.isVisible()
        assert not w.hud.isVisible()
