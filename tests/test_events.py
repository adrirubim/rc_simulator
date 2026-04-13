from __future__ import annotations

from rc_simulator.core.events import (
    CarsEvent,
    ErrorEvent,
    LogEvent,
    MozaStateEvent,
    ScanDoneEvent,
    SessionStoppedEvent,
    StatusEvent,
    TelemetryEvent,
)
from rc_simulator.core.models import Car


def test_events_are_instantiable() -> None:
    StatusEvent(summary="x", detail="y")
    LogEvent(level="INFO", message="m")
    ErrorEvent(message="e")
    CarsEvent(cars=[Car(car_id="c1", name="car", ip="1.2.3.4", control_port=9999, video_port=5600)])
    ScanDoneEvent()
    MozaStateEvent(connected=True)
    TelemetryEvent(payload={"steer": 0.0, "gas": 0.0, "brake": 0.0, "output": 0.0, "text": "ok"})
    SessionStoppedEvent(reason="disconnect")
