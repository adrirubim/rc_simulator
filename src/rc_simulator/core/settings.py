from __future__ import annotations

from typing import Any, Protocol


class SettingsStore(Protocol):
    def value(self, key: str, defaultValue: Any | None = None) -> Any: ...

    def setValue(self, key: str, value: Any) -> None: ...
