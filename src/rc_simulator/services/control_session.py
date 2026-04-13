from __future__ import annotations

import select
import socket
import time
from typing import Any

from evdev import InputDevice, ecodes

from ..core.config import load_config
from ..core.events import ErrorEvent, LogEvent, MozaStateEvent, SessionStoppedEvent, StatusEvent, TelemetryEvent
from ..core.state import AppPhase, TelemetryPayload
from .control_math import apply_deadzone, clamp, norm_axis, norm_trigger
from .steer_unwrap import SteerUnwrapper

# =====================
# ASSI (confermati)
# 0 volante / 2 gas / 5 freno
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

# invio (defaults; overridden by config at runtime)
SEND_HZ_DEFAULT = 120

# deadzone
STEER_DEADZONE_DEFAULT = 0.02
PEDAL_DEADZONE_DEFAULT = 0.02


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
            raise RuntimeError(f"{label} axis non trovato (code={code}).")

    return dev, abs_map


def drive_worker(car: dict[str, Any], stop_event, ui_queue) -> None:
    """
    Sessione di guida verso la macchina selezionata.
    Gira in thread separato per non bloccare la GUI.
    """
    orange_ip = car["ip"]
    orange_port = car["control_port"]

    ui_queue.put(
        StatusEvent(
            summary="Connesso",
            detail=f"{car['name']} ({orange_ip}:{orange_port})",
            phase=AppPhase.CONNECTED,
        )
    )
    ui_queue.put(LogEvent(level="INFO", message=f"Connesso a {car['name']}"))
    ui_queue.put(LogEvent(level="INFO", message=f"IP: {orange_ip}"))
    ui_queue.put(LogEvent(level="INFO", message=f"Porta controllo: {orange_port}"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dev = None

    try:
        cfg = load_config()

        dev_path = str(getattr(cfg, "moza_dev_path", "")) or "/dev/input/event0"
        send_hz = int(getattr(cfg, "control_send_hz", SEND_HZ_DEFAULT) or SEND_HZ_DEFAULT)
        send_hz = max(1, min(send_hz, 1000))
        send_dt = 1.0 / float(send_hz)

        steer_invert = bool(getattr(cfg, "steer_invert", STEER_INVERT_DEFAULT))
        throttle_invert = bool(getattr(cfg, "throttle_invert", THROTTLE_INVERT_DEFAULT))
        brake_invert = bool(getattr(cfg, "brake_invert", BRAKE_INVERT_DEFAULT))

        steer_gain = float(getattr(cfg, "steer_gain", STEER_GAIN_DEFAULT) or STEER_GAIN_DEFAULT)
        steer_limit = float(getattr(cfg, "steer_limit", STEER_LIMIT_DEFAULT) or STEER_LIMIT_DEFAULT)
        steer_deadzone = float(getattr(cfg, "steer_deadzone", STEER_DEADZONE_DEFAULT) or STEER_DEADZONE_DEFAULT)
        pedal_deadzone = float(getattr(cfg, "pedal_deadzone", PEDAL_DEADZONE_DEFAULT) or PEDAL_DEADZONE_DEFAULT)

        dev, abs_map = open_moza_device(dev_path)
        ui_queue.put(MozaStateEvent(connected=True))
        ui_queue.put(LogEvent(level="INFO", message=f"MOZA: {dev.path} - {dev.name}"))

        steer = 0.0
        gas01 = 0.0
        brake01 = 0.0

        steer_info = abs_map[STEER_CODE]
        steer_min = int(steer_info.min)
        steer_max = int(steer_info.max)

        unwrapper = SteerUnwrapper(steer_min=steer_min, steer_max=steer_max, wrap_jump_frac=WRAP_JUMP_FRAC)

        last_send = 0.0
        last_ui = 0.0

        while not stop_event.is_set():
            readable, _, _ = select.select([dev.fd], [], [], 0.02)

            if readable:
                for event in dev.read():
                    if event.type != ecodes.EV_ABS:
                        continue

                    code = event.code
                    val = int(event.value)

                    if code == STEER_CODE:
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
                ui_queue.put(
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
                    )
                )

    except Exception as e:
        ui_queue.put(MozaStateEvent(connected=False))
        ui_queue.put(ErrorEvent(message=f"Errore nella sessione di controllo: {e}"))
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

        ui_queue.put(
            TelemetryEvent(
                payload=TelemetryPayload(
                    steer=0.0,
                    gas=0.0,
                    brake=0.0,
                    output=0.0,
                    text="Sessione ferma",
                ).__dict__
            )
        )
        ui_queue.put(StatusEvent(summary="Disconnesso", detail="", phase=AppPhase.IDLE))
        ui_queue.put(MozaStateEvent(connected=False))
        ui_queue.put(SessionStoppedEvent(reason="worker-exit"))
