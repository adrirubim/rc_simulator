from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass

from ..core.control_config import ControlConfig
from ..core.events import CarsEvent, LogEvent, ScanDoneEvent, StatusEvent, UiEvent
from ..core.models import Car
from ..core.queue_utils import put_with_backpressure
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
    scan_stop_event: threading.Event | None = None
    drive_stop_event: threading.Event | None = None
    control_cfg: ControlConfig = ControlConfig()
    events_dropped: int = 0
    events_drop_oldest: int = 0

    def _put_event(self, ev: UiEvent, *, allow_drop: bool) -> None:
        put_with_backpressure(
            self.events,
            ev,
            allow_drop=allow_drop,
            on_drop=lambda: setattr(self, "events_dropped", int(self.events_dropped) + 1),
            on_drop_oldest=lambda: setattr(self, "events_drop_oldest", int(self.events_drop_oldest) + 1),
        )

    @classmethod
    def create_default(cls, *, control_cfg: ControlConfig | None = None) -> SessionController:
        max_events = int(os.getenv("RC_EVENT_QUEUE_MAX", "2000") or "2000")
        max_events = max(200, min(max_events, 50_000))
        return cls(
            events=queue.Queue(maxsize=max_events),
            control_cfg=control_cfg or ControlConfig.from_env(),
        )

    def start_scan(self) -> bool:
        if self.drive_thread is not None and self.drive_thread.is_alive():
            return False
        if self.scan_thread is not None and self.scan_thread.is_alive():
            return False

        # Scan cancellation must not affect drive sessions (current or future).
        self.scan_stop_event = threading.Event()

        self._put_event(StatusEvent(summary="Scanning…", detail="", phase=AppPhase.SCANNING), allow_drop=False)
        self.scan_thread = threading.Thread(target=self._scan_worker, args=(self.scan_stop_event,), daemon=False)
        self.scan_thread.start()
        return True

    def cancel_scan(self) -> bool:
        """
        Best-effort cancel for an in-progress scan.
        Returns True if a scan was active and we requested cancellation.
        """
        if self.scan_thread is None or not self.scan_thread.is_alive():
            return False
        if self.scan_stop_event is None:
            return False
        try:
            self.scan_stop_event.set()
        except Exception:
            pass
        # Keep phase as SCANNING; ScanDoneEvent will follow from the worker finally block.
        self._put_event(
            StatusEvent(summary="Scanning…", detail="Cancelling…", phase=AppPhase.SCANNING),
            allow_drop=False,
        )
        return True

    def _scan_worker(self, stop_event: threading.Event) -> None:
        try:
            self._put_event(StatusEvent(summary="Scanning…", detail="", phase=AppPhase.SCANNING), allow_drop=False)
            self._put_event(
                LogEvent(level="INFO", message="Searching for RC cars on the network…"),
                allow_drop=True,
            )

            cars_dict = discover_cars(timeout_s=3.0, stop_event=stop_event)
            cars = list(cars_dict.values())
            cars.sort(key=lambda c: (c.name, c.ip))
            self._put_event(CarsEvent(cars=cars), allow_drop=True)
        finally:
            # Always unblock UI state transitions even if scan is cancelled or errors.
            self._put_event(ScanDoneEvent(), allow_drop=False)

    def connect(self, car: Car) -> bool:
        if self.drive_thread is not None and self.drive_thread.is_alive():
            return False

        self._put_event(
            StatusEvent(
                summary="Connecting…",
                detail=f"{car.name} ({car.ip}:{car.control_port})",
                phase=AppPhase.CONNECTING,
            ),
            allow_drop=False,
        )
        # Drive cancellation must be isolated from discovery cancellation.
        self.drive_stop_event = threading.Event()
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
                self.drive_stop_event,
                self.events,
            ),
            kwargs={"control_cfg": self.control_cfg},
            daemon=False,
        )
        self.drive_thread.start()
        return True

    def disconnect(self) -> None:
        if self.drive_stop_event is None:
            return
        self._put_event(
            StatusEvent(summary="Disconnecting…", detail="", phase=AppPhase.DISCONNECTING),
            allow_drop=False,
        )
        try:
            self.drive_stop_event.set()
        except Exception:
            pass

    def shutdown(self, timeout_s: float = 2.0) -> None:
        """
        Deterministic shutdown:
        - signals both scan and drive stop events
        - synchronously joins both worker threads (best-effort within timeout)
        """
        timeout_s = float(timeout_s)
        timeout_s = 0.0 if timeout_s < 0.0 else timeout_s

        # Signal both workers.
        try:
            if self.scan_stop_event is not None:
                self.scan_stop_event.set()
        except Exception:
            pass
        try:
            if self.drive_stop_event is not None:
                self.drive_stop_event.set()
        except Exception:
            pass

        # Join both threads synchronously, sharing the same overall budget.
        deadline = None
        try:
            import time

            deadline = time.time() + timeout_s
        except Exception:
            deadline = None

        def _remaining() -> float | None:
            if deadline is None:
                return timeout_s
            try:
                import time

                rem = deadline - time.time()
                return 0.0 if rem < 0.0 else rem
            except Exception:
                return timeout_s

        t_scan = self.scan_thread
        t_drive = self.drive_thread

        try:
            if t_scan is not None and t_scan.is_alive():
                t_scan.join(timeout=_remaining() or 0.0)
        except Exception:
            pass
        try:
            if t_drive is not None and t_drive.is_alive():
                t_drive.join(timeout=_remaining() or 0.0)
        except Exception:
            pass

        # Clear references only when threads are finished.
        try:
            if self.scan_thread is t_scan and (t_scan is None or not t_scan.is_alive()):
                self.scan_thread = None
                self.scan_stop_event = None
        except Exception:
            pass
        try:
            if self.drive_thread is t_drive and (t_drive is None or not t_drive.is_alive()):
                self.drive_thread = None
                self.drive_stop_event = None
        except Exception:
            pass
