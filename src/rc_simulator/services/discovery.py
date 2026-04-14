from __future__ import annotations

import json
import socket
import time
from typing import Any

from ..core.models import Car

# =====================
# DISCOVERY
# =====================
DISCOVERY_PORT = 37020
DISCOVERY_TIMEOUT_S = 3.0
DISCOVERY_STALE_S = 3.0

# fallback control port
DEFAULT_CONTROL_PORT = 5005


def discover_cars(*, timeout_s: float = DISCOVERY_TIMEOUT_S, stop_event=None) -> dict[str, Car]:
    """
    Listen for UDP broadcast beacons and build a list of live cars.
    Returns a dict keyed by car_id.
    """
    cars: dict[str, dict[str, Any]] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", DISCOVERY_PORT))
        sock.settimeout(0.5)

        t0 = time.time()

        while time.time() - t0 < timeout_s:
            if stop_event is not None:
                try:
                    if stop_event.is_set():
                        break
                except Exception:
                    # Best-effort: if the event is misbehaving, keep discovery functional.
                    pass
            try:
                data, addr = sock.recvfrom(4096)
                msg = json.loads(data.decode("utf-8", errors="ignore"))

                if msg.get("type") != "car_hello":
                    continue

                car_id = msg.get("car_id", "unknown")
                cars[car_id] = {
                    "car_id": car_id,
                    "name": msg.get("name", car_id),
                    "ip": msg.get("ip", addr[0]),
                    "control_port": int(msg.get("control_port", DEFAULT_CONTROL_PORT)),
                    "video_port": int(msg.get("video_port", 5600)),
                    "last_seen": time.time(),
                }

            except TimeoutError:
                continue
            except Exception:
                continue
    finally:
        try:
            sock.close()
        except Exception:
            pass

    now = time.time()
    cars = {cid: car for cid, car in cars.items() if now - car["last_seen"] <= DISCOVERY_STALE_S}
    return {
        cid: Car(
            car_id=str(car.get("car_id", cid) or cid),
            name=str(car.get("name", cid) or cid),
            ip=str(car.get("ip", "") or ""),
            control_port=int(car.get("control_port", DEFAULT_CONTROL_PORT)),
            video_port=int(car.get("video_port", 5600)),
        )
        for cid, car in cars.items()
    }
