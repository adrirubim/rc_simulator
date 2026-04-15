from __future__ import annotations

import os
import queue
import threading
from dataclasses import dataclass

from ..core.control_config import ControlConfig
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
    control_cfg: ControlConfig = ControlConfig()

    def _put_event(self, ev: UiEvent, *, allow_drop: bool) -> None:
        """
        Best-effort enqueue with bounded backpressure.

        - If the queue is full and `allow_drop` is True, drop the event.
        - Otherwise, drop one oldest event and retry once.
        """
        try:
            self.events.put_nowait(ev)
            return
        except queue.Full:
            if allow_drop:
                return
        try:
            _ = self.events.get_nowait()
        except Exception:
            return
        try:
            self.events.put_nowait(ev)
        except Exception:
            return

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

        # Ensure scans are cancellable via the same stop_event used for sessions.
        # If a previous stop_event exists (e.g. after a disconnect), replace it with a fresh one.
        if self.stop_event is None or self.stop_event.is_set():
            self.stop_event = threading.Event()

        self._put_event(StatusEvent(summary="Scanning…", detail="", phase=AppPhase.SCANNING), allow_drop=False)
        self.scan_thread = threading.Thread(target=self._scan_worker, args=(self.stop_event,), daemon=True)
        self.scan_thread.start()
        return True

    def cancel_scan(self) -> bool:
        """
        Best-effort cancel for an in-progress scan.
        Returns True if a scan was active and we requested cancellation.
        """
        if self.scan_thread is None or not self.scan_thread.is_alive():
            return False
        if self.stop_event is None:
            return False
        try:
            self.stop_event.set()
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
            kwargs={"control_cfg": self.control_cfg},
            daemon=True,
        )
        self.drive_thread.start()
        return True

    def disconnect(self) -> None:
        if self.stop_event is None:
            return
        self._put_event(
            StatusEvent(summary="Disconnecting…", detail="", phase=AppPhase.DISCONNECTING),
            allow_drop=False,
        )
        try:
            self.stop_event.set()
        except Exception:
            pass

        # Join in background (do not block UI). We don't emit SessionStoppedEvent here because
        # `drive_worker` already emits it in its `finally` block.
        drive_thread = self.drive_thread
        scan_thread = self.scan_thread

        def _join() -> None:
            if drive_thread is not None and drive_thread.is_alive():
                drive_thread.join(timeout=1.0)
            if scan_thread is not None and scan_thread.is_alive():
                scan_thread.join(timeout=1.0)

            # Only clear references for threads that are actually finished.
            if self.drive_thread is drive_thread and (drive_thread is None or not drive_thread.is_alive()):
                self.drive_thread = None
            if self.scan_thread is scan_thread and (scan_thread is None or not scan_thread.is_alive()):
                self.scan_thread = None

            # Only clear stop_event once all background activity is finished.
            any_alive = False
            try:
                any_alive = bool(
                    (self.drive_thread is not None and self.drive_thread.is_alive())
                    or (self.scan_thread is not None and self.scan_thread.is_alive())
                )
            except Exception:
                any_alive = True
            if not any_alive:
                self.stop_event = None

        threading.Thread(target=_join, daemon=True).start()

    def shutdown(self) -> None:
        self.disconnect()
