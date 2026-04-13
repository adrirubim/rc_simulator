from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .models import Car


@dataclass(frozen=True, slots=True)
class StatusEvent:
    summary: str
    detail: str = ""
    phase: Any | None = None


@dataclass(frozen=True, slots=True)
class LogEvent:
    level: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR", "OK", "SUCCESS"] | str
    message: str


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    message: str


@dataclass(frozen=True, slots=True)
class CarsEvent:
    cars: list[Car]


@dataclass(frozen=True, slots=True)
class ScanDoneEvent:
    pass


@dataclass(frozen=True, slots=True)
class MozaStateEvent:
    connected: bool


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SessionStoppedEvent:
    reason: str = "stopped"


type UiEvent = (
    StatusEvent
    | LogEvent
    | ErrorEvent
    | CarsEvent
    | ScanDoneEvent
    | MozaStateEvent
    | TelemetryEvent
    | SessionStoppedEvent
)
