from __future__ import annotations


def test_session_controller_uses_bounded_queue(monkeypatch) -> None:
    monkeypatch.setenv("RC_EVENT_QUEUE_MAX", "333")
    from rc_simulator.app.session_controller import SessionController

    c = SessionController.create_default()
    assert getattr(c.events, "maxsize", None) == 333


def test_session_controller_counts_drops(monkeypatch) -> None:
    monkeypatch.setenv("RC_EVENT_QUEUE_MAX", "200")
    from rc_simulator.app.session_controller import SessionController
    from rc_simulator.core.events import LogEvent

    c = SessionController.create_default()
    # Fill queue to capacity.
    for _ in range(int(getattr(c.events, "maxsize", 0) or 0)):
        c.events.put_nowait(LogEvent(level="DEBUG", message="x"))

    before = c.events_dropped
    c._put_event(LogEvent(level="DEBUG", message="drop"), allow_drop=True)  # type: ignore[attr-defined]
    assert c.events_dropped == before + 1
