from __future__ import annotations

import queue
import threading
from dataclasses import dataclass

from ..core.events import CarsEvent, LogEvent, ScanDoneEvent, StatusEvent, UiEvent
from ..core.models import Car
from ..core.state import AppPhase
from ..services import discover_cars, drive_worker


@dataclass(slots=True)
class SessionController:
    """
    Owns background threads and publishes UiEvent to a queue.

    UI should call start_scan/connect/disconnect and drain `events`.
    """

    events: queue.Queue[UiEvent]
    scan_thread: threading.Thread | None = None
    drive_thread: threading.Thread | None = None
    stop_event: threading.Event | None = None

    @classmethod
    def create_default(cls) -> SessionController:
        return cls(events=queue.Queue())

    def start_scan(self) -> bool:
        if self.drive_thread is not None and self.drive_thread.is_alive():
            return False
        if self.scan_thread is not None and self.scan_thread.is_alive():
            return False

        self.events.put(StatusEvent(summary="Scansione…", detail="", phase=AppPhase.SCANNING))
        self.scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self.scan_thread.start()
        return True

    def _scan_worker(self) -> None:
        self.events.put(StatusEvent(summary="Scansione…", detail="", phase=AppPhase.SCANNING))
        self.events.put(LogEvent(level="INFO", message="Ricerca di auto RC in rete…"))
        cars_dict = discover_cars()
        cars = list(cars_dict.values())
        cars.sort(key=lambda c: (c.name, c.ip))
        self.events.put(CarsEvent(cars=cars))
        self.events.put(ScanDoneEvent())

    def connect(self, car: Car) -> bool:
        if self.drive_thread is not None and self.drive_thread.is_alive():
            return False

        self.events.put(
            StatusEvent(
                summary="Connessione…",
                detail=f"{car.name} ({car.ip}:{car.control_port})",
                phase=AppPhase.CONNECTING,
            )
        )
        self.stop_event = threading.Event()
        self.drive_thread = threading.Thread(
            target=drive_worker,
            args=(
                {
                    "car_id": car.car_id,
                    "name": car.name,
                    "ip": car.ip,
                    "control_port": car.control_port,
                    "video_port": car.video_port,
                },
                self.stop_event,
                self.events,
            ),
            daemon=True,
        )
        self.drive_thread.start()
        return True

    def disconnect(self) -> None:
        if self.stop_event is None:
            return
        self.events.put(StatusEvent(summary="Disconnessione…", detail="", phase=AppPhase.DISCONNECTING))
        try:
            self.stop_event.set()
        except Exception:
            pass

        # Join in background (do not block UI). We don't emit SessionStoppedEvent here because
        # `drive_worker` already emits it in its `finally` block.
        drive_thread = self.drive_thread
        scan_thread = self.scan_thread

        def _join() -> None:
            try:
                if drive_thread is not None and drive_thread.is_alive():
                    drive_thread.join(timeout=1.0)
                if scan_thread is not None and scan_thread.is_alive():
                    scan_thread.join(timeout=1.0)
            finally:
                # Best-effort cleanup of internal references
                self.drive_thread = None
                self.scan_thread = None
                self.stop_event = None

        threading.Thread(target=_join, daemon=True).start()

    def shutdown(self) -> None:
        self.disconnect()
