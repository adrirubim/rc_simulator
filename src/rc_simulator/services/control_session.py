from __future__ import annotations

import queue
import select
import socket
import time
from pathlib import Path
from typing import Any

from evdev import InputDevice, ecodes

from ..core.control_config import ControlConfig
from ..core.events import ErrorEvent, LogEvent, MozaStateEvent, SessionStoppedEvent, StatusEvent, TelemetryEvent
from ..core.state import AppPhase, TelemetryPayload
from .control_math import apply_deadzone, clamp, norm_axis, norm_trigger
from .steer_unwrap import SteerUnwrapper

# =====================
# AXES (confirmed)
# 0 steering / 2 throttle / 5 brake
# =====================
STEER_CODE = ecodes.ABS_X
THROTTLE_CODE = ecodes.ABS_Z
BRAKE_CODE = ecodes.ABS_RZ

# =====================
# INVERSIONI (defaults; overridden by config at runtime)
# =====================
STEER_INVERT_DEFAULT = True
THROTTLE_INVERT_DEFAULT = False
BRAKE_INVERT_DEFAULT = False

# =====================
# STERZO (defaults; overridden by config at runtime)
# =====================
STEER_GAIN_DEFAULT = 2.2
STEER_LIMIT_DEFAULT = 1.0

# anti-wrap
WRAP_JUMP_FRAC = 0.45

# send (defaults; overridden by config at runtime)
SEND_HZ_DEFAULT = 120

# deadzone
STEER_DEADZONE_DEFAULT = 0.02
PEDAL_DEADZONE_DEFAULT = 0.02


def _list_input_candidates() -> list[str]:
    out: list[str] = []
    for p in sorted(Path("/dev/input/by-id").glob("*event*")):
        out.append(str(p))
        if len(out) >= 12:
            return out
    for p in sorted(Path("/dev/input/by-path").glob("*event*")):
        out.append(str(p))
        if len(out) >= 12:
            return out
    for p in sorted(Path("/dev/input").glob("event*")):
        out.append(str(p))
        if len(out) >= 12:
            return out
    return out


def open_moza_device(dev_path: str) -> tuple[InputDevice, dict[int, Any]]:
    dev = InputDevice(dev_path)

    caps = dev.capabilities(absinfo=True)
    absinfo = caps.get(ecodes.EV_ABS, [])
    abs_map = {code: info for code, info in absinfo}

    for code, label in [
        (STEER_CODE, "STEER"),
        (THROTTLE_CODE, "THROTTLE"),
        (BRAKE_CODE, "BRAKE"),
    ]:
        if code not in abs_map:
            raise RuntimeError(f"{label} axis not found (code={code}).")

    return dev, abs_map


def drive_worker(car: dict[str, Any], stop_event, ui_queue, *, control_cfg: ControlConfig) -> None:
    """
    Drive session worker for the selected car.
    Runs in a separate thread to avoid blocking the GUI.
    """
    orange_ip = car["ip"]
    orange_port = car["control_port"]

    def _put(ev, *, allow_drop: bool) -> None:
        try:
            ui_queue.put_nowait(ev)
            return
        except Exception as e:
            if isinstance(e, queue.Full):
                if allow_drop:
                    return
                try:
                    _ = ui_queue.get_nowait()
                except Exception:
                    return
                try:
                    ui_queue.put_nowait(ev)
                except Exception:
                    return
            return

    _put(
        StatusEvent(
            summary="Connected",
            detail=f"{car['name']} ({orange_ip}:{orange_port})",
            phase=AppPhase.CONNECTED,
        ),
        allow_drop=False,
    )
    _put(LogEvent(level="INFO", message=f"Connected to {car['name']}"), allow_drop=True)
    _put(LogEvent(level="INFO", message=f"IP: {orange_ip}"), allow_drop=True)
    _put(LogEvent(level="INFO", message=f"Control port: {orange_port}"), allow_drop=True)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dev = None

    try:
        dev_path = str(control_cfg.moza_dev_path or "/dev/input/event0")
        allow_no_moza = bool(control_cfg.allow_no_moza)
        send_hz = int(control_cfg.control_send_hz or SEND_HZ_DEFAULT)
        send_hz = max(1, min(send_hz, 1000))
        send_dt = 1.0 / float(send_hz)

        steer_invert = bool(control_cfg.steer_invert)
        throttle_invert = bool(control_cfg.throttle_invert)
        brake_invert = bool(control_cfg.brake_invert)

        steer_gain = float(control_cfg.steer_gain or STEER_GAIN_DEFAULT)
        steer_limit = float(control_cfg.steer_limit or STEER_LIMIT_DEFAULT)
        steer_deadzone = float(control_cfg.steer_deadzone or STEER_DEADZONE_DEFAULT)
        pedal_deadzone = float(control_cfg.pedal_deadzone or PEDAL_DEADZONE_DEFAULT)

        abs_map: dict[int, Any] | None = None
        try:
            dev, abs_map = open_moza_device(dev_path)
            _put(MozaStateEvent(connected=True), allow_drop=False)
            _put(LogEvent(level="INFO", message=f"MOZA: {dev.path} - {dev.name}"), allow_drop=True)
        except FileNotFoundError as e:
            _put(MozaStateEvent(connected=False), allow_drop=False)
            candidates = _list_input_candidates()
            if candidates:
                _put(
                    LogEvent(level="INFO", message="Input candidates:\n- " + "\n- ".join(candidates)),
                    allow_drop=True,
                )
            if not allow_no_moza:
                raise FileNotFoundError(
                    f"MOZA device not found at {dev_path!r}. Set RC_UI_MOZA_DEV_PATH to one of:\n- "
                    + "\n- ".join(candidates or ["(no /dev/input candidates found)"])
                ) from e
            _put(
                LogEvent(
                    level="WARN",
                    message=(
                        f"MOZA device not found at {dev_path!r}. Running in no-input mode. "
                        "Set RC_UI_MOZA_DEV_PATH to the correct /dev/input/... path to enable MOZA input."
                    ),
                ),
                allow_drop=False,
            )
            _put(LogEvent(level="DEBUG", message=f"MOZA open error: {e}"), allow_drop=True)
        except Exception as e:
            _put(MozaStateEvent(connected=False), allow_drop=False)
            if not allow_no_moza:
                raise
            _put(
                LogEvent(
                    level="WARN",
                    message=(
                        f"MOZA init failed ({e}). Running in no-input mode. "
                        "Set RC_UI_MOZA_DEV_PATH to the correct /dev/input/... path to enable MOZA input."
                    ),
                ),
                allow_drop=False,
            )

        steer = 0.0
        gas01 = 0.0
        brake01 = 0.0

        if abs_map is not None:
            steer_info = abs_map[STEER_CODE]
            steer_min = int(steer_info.min)
            steer_max = int(steer_info.max)
            unwrapper = SteerUnwrapper(steer_min=steer_min, steer_max=steer_max, wrap_jump_frac=WRAP_JUMP_FRAC)
        else:
            steer_min = -1
            steer_max = 1
            unwrapper = None

        last_send = 0.0
        last_ui = 0.0

        while not stop_event.is_set():
            if dev is not None:
                readable, _, _ = select.select([dev.fd], [], [], 0.02)
            else:
                readable = []
                time.sleep(0.02)

            if readable:
                for event in dev.read():
                    if event.type != ecodes.EV_ABS:
                        continue

                    code = event.code
                    val = int(event.value)

                    if code == STEER_CODE:
                        if unwrapper is None:
                            continue
                        val_wrapped = unwrapper.update(val)
                        s = norm_axis(val_wrapped, steer_min, steer_max, invert=steer_invert)
                        s = apply_deadzone(s, steer_deadzone)
                        s = clamp(s * steer_gain, -1.0, 1.0)
                        s = clamp(s, -steer_limit, +steer_limit)
                        steer = s

                    elif code == THROTTLE_CODE:
                        info = abs_map[code]
                        gas01 = norm_trigger(val, info.min, info.max, invert=throttle_invert)
                        if gas01 < pedal_deadzone:
                            gas01 = 0.0

                    elif code == BRAKE_CODE:
                        info = abs_map[code]
                        brake01 = norm_trigger(val, info.min, info.max, invert=brake_invert)
                        if brake01 < pedal_deadzone:
                            brake01 = 0.0

            throttle = clamp(gas01 - brake01, -1.0, 1.0)
            now = time.time()

            if now - last_send >= send_dt:
                last_send = now
                msg = f"{now:.6f} {throttle:.4f} {steer:.4f}"
                sock.sendto(msg.encode("ascii"), (orange_ip, orange_port))

            if now - last_ui >= 0.10:
                last_ui = now
                _put(
                    TelemetryEvent(
                        payload=TelemetryPayload(
                            steer=steer,
                            gas=gas01,
                            brake=brake01,
                            output=throttle,
                            text=(
                                f"steer={steer:+.3f}  gas={gas01:.3f}  brake={brake01:.3f}  -> throttle={throttle:+.3f}"
                            ),
                        ).__dict__
                    ),
                    allow_drop=True,
                )

    except Exception as e:
        _put(MozaStateEvent(connected=False), allow_drop=False)
        _put(ErrorEvent(message=f"Control session error: {e}"), allow_drop=False)
    finally:
        try:
            stop_msg = f"{time.time():.6f} 0.0000 0.0000"
            sock.sendto(stop_msg.encode("ascii"), (orange_ip, orange_port))
        except Exception:
            pass

        sock.close()

        if dev is not None:
            try:
                dev.close()
            except Exception:
                pass

        _put(
            TelemetryEvent(
                payload=TelemetryPayload(
                    steer=0.0,
                    gas=0.0,
                    brake=0.0,
                    output=0.0,
                    text="Session stopped",
                ).__dict__
            ),
            allow_drop=True,
        )
        _put(StatusEvent(summary="Disconnected", detail="", phase=AppPhase.IDLE), allow_drop=False)
        _put(MozaStateEvent(connected=False), allow_drop=False)
        _put(SessionStoppedEvent(reason="worker-exit"), allow_drop=False)
