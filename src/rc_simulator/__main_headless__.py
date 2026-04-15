from __future__ import annotations

import argparse
import logging
import queue
import signal
import sys
import time
from collections.abc import Iterable
from dataclasses import asdict

from .app.session_controller import SessionController
from .core.control_config import ControlConfig
from .core.events import (
    CarsEvent,
    ErrorEvent,
    LogEvent,
    MozaStateEvent,
    ScanDoneEvent,
    SessionStoppedEvent,
    StatusEvent,
    TelemetryEvent,
    UiEvent,
)
from .core.models import Car
from .services.discovery import DEFAULT_CONTROL_PORT


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m rc_simulator.__main_headless__",
        description="RC Simulator: headless mode (MOZA/UDP) without Qt/PySide6.",
    )
    p.add_argument(
        "--discover-timeout-s",
        type=float,
        default=3.0,
        help="Maximum UDP discovery time (seconds).",
    )
    p.add_argument(
        "--car-id",
        type=str,
        default="",
        help="Connect to the car with this car_id (if discovered).",
    )
    p.add_argument(
        "--ip",
        type=str,
        default="",
        help="Car IP (skips discovery when provided).",
    )
    p.add_argument(
        "--control-port",
        type=int,
        default=0,
        help=f"Control UDP port (default {DEFAULT_CONTROL_PORT}). Requires --ip.",
    )
    p.add_argument(
        "--name",
        type=str,
        default="headless-car",
        help="Name to display when using --ip/--control-port.",
    )
    p.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    p.add_argument(
        "--allow-no-moza",
        action="store_true",
        help="Do not fail if the MOZA device is missing; run in no-input mode (sends 0/0).",
    )
    p.add_argument(
        "--moza-dev-path",
        type=str,
        default="",
        help="Override RC_UI_MOZA_DEV_PATH (/dev/input/... path for MOZA).",
    )
    return p


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )


def _event_to_log_lines(ev: UiEvent) -> Iterable[tuple[int, str]]:
    """
    Convert UI events (reused by the controller) into log lines.
    Returns tuples (logging_level, message).
    """
    if isinstance(ev, LogEvent):
        level = str(ev.level).upper()
        if level in ("OK", "SUCCESS"):
            return [(logging.INFO, ev.message)]
        if level in ("WARN", "WARNING"):
            return [(logging.WARNING, ev.message)]
        if level == "DEBUG":
            return [(logging.DEBUG, ev.message)]
        if level == "ERROR":
            return [(logging.ERROR, ev.message)]
        return [(logging.INFO, ev.message)]

    if isinstance(ev, StatusEvent):
        detail = f" - {ev.detail}" if ev.detail else ""
        return [(logging.INFO, f"{ev.summary}{detail}")]

    if isinstance(ev, ErrorEvent):
        return [(logging.ERROR, ev.message)]

    if isinstance(ev, CarsEvent):
        cars = ", ".join([f"{c.name}({c.car_id})@{c.ip}:{c.control_port}" for c in ev.cars]) or "(none)"
        return [(logging.INFO, f"Cars discovered: {cars}")]

    if isinstance(ev, ScanDoneEvent):
        return [(logging.INFO, "Discovery scan done")]

    if isinstance(ev, MozaStateEvent):
        return [(logging.INFO, f"MOZA connected={ev.connected}")]

    if isinstance(ev, TelemetryEvent):
        payload = ev.payload or {}
        txt = str(payload.get("text", "") or "").strip()
        if txt:
            return [(logging.DEBUG, txt)]
        return [(logging.DEBUG, f"Telemetry: {payload}")]

    if isinstance(ev, SessionStoppedEvent):
        return [(logging.INFO, f"Session stopped (reason={ev.reason})")]

    return [(logging.DEBUG, f"Event: {ev!r}")]


def _pick_car(cars: list[Car], car_id: str) -> Car | None:
    if not cars:
        return None
    if car_id:
        for c in cars:
            if c.car_id == car_id:
                return c
    # deterministic: first by name, then IP
    cars_sorted = sorted(cars, key=lambda c: (c.name, c.ip))
    return cars_sorted[0]


def run_headless(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _setup_logging(args.log_level)

    log = logging.getLogger("rc_simulator.headless")
    log.info("Starting headless control session")

    control_cfg = ControlConfig.from_env()
    if args.moza_dev_path:
        control_cfg = ControlConfig(**{**control_cfg.__dict__, "moza_dev_path": str(args.moza_dev_path)})
    if args.allow_no_moza:
        control_cfg = ControlConfig(**{**control_cfg.__dict__, "allow_no_moza": True})

    controller = SessionController.create_default(control_cfg=control_cfg)

    stop_requested = False

    def _request_stop(_signum: int, _frame) -> None:  # type: ignore[no-untyped-def]
        nonlocal stop_requested
        stop_requested = True
        log.info("Stop requested (signal). Disconnecting…")
        try:
            controller.shutdown()
        except Exception:
            pass

    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)

    chosen_car: Car | None = None
    if args.ip:
        chosen_car = Car(
            car_id=args.car_id or "manual",
            name=args.name or args.ip,
            ip=args.ip,
            control_port=int(args.control_port or DEFAULT_CONTROL_PORT),
            video_port=5600,
        )
        log.info("Using manual target: %s", asdict(chosen_car))
    else:
        controller.start_scan()
        cars: list[Car] = []

        scan_deadline = time.time() + float(max(0.1, args.discover_timeout_s))
        while time.time() < scan_deadline and not stop_requested:
            try:
                ev = controller.events.get(timeout=0.2)
            except queue.Empty:
                continue

            for lvl, msg in _event_to_log_lines(ev):
                log.log(lvl, msg)

            if isinstance(ev, CarsEvent):
                cars = ev.cars
            if isinstance(ev, ScanDoneEvent):
                break

        chosen_car = _pick_car(cars, args.car_id)
        if chosen_car is None:
            log.error("No cars found via discovery. Use --ip/--control-port or check your network.")
            return 2

    if stop_requested:
        return 0

    log.info("Connecting to car: %s", asdict(chosen_car))
    if not controller.connect(chosen_car):
        log.error("Unable to start the session (a session may already be active).")
        return 3

    # Main loop: drain events and wait for signals / worker stop.
    session_stopped = False
    while not stop_requested and not session_stopped:
        try:
            ev = controller.events.get(timeout=0.5)
        except queue.Empty:
            continue

        for lvl, msg in _event_to_log_lines(ev):
            log.log(lvl, msg)

        if isinstance(ev, SessionStoppedEvent):
            session_stopped = True
        if isinstance(ev, ErrorEvent):
            # The worker reports the error and then stops; keep looping until SessionStoppedEvent
            pass

    try:
        controller.shutdown()
    except Exception:
        pass

    log.info("Headless session exited cleanly")
    return 0


def main_cli() -> None:
    raise SystemExit(run_headless())


if __name__ == "__main__":
    main_cli()
