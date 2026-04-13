from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VideoFrame:
    width: int
    height: int
    rgb_bytes: bytes  # packed BGRA (BGRA8888)


class VideoReceiver(ABC):
    @abstractmethod
    def start(self) -> bool: ...

    @abstractmethod
    def stop(self) -> None: ...


class VideoReceiverFactory(Protocol):
    def __call__(
        self,
        *,
        port: int,
        latency_ms: int,
        on_frame: Callable[[VideoFrame], None],
        on_error: Callable[[str], None],
    ) -> VideoReceiver: ...
