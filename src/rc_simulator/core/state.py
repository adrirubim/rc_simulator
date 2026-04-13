from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AppPhase(StrEnum):
    IDLE = "idle"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


@dataclass(frozen=True)
class StatusPayload:
    summary: str
    detail: str = ""
    phase: AppPhase | None = None


@dataclass(frozen=True)
class TelemetryPayload:
    steer: float
    gas: float
    brake: float
    output: float
    text: str
