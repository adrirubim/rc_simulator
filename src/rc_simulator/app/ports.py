from __future__ import annotations

from typing import Protocol

from ..core.models import Car


class SessionControllerPort(Protocol):
    """
    UI-facing controller contract.

    Intentionally hides concurrency details (threads/events) behind a stable surface.
    """

    events: object

    def start_scan(self) -> bool: ...

    def cancel_scan(self) -> bool: ...

    def connect(self, car: Car) -> bool: ...

    def disconnect(self) -> None: ...

    def shutdown(self) -> None: ...
