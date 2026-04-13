from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Car:
    car_id: str
    name: str
    ip: str
    control_port: int
    video_port: int
