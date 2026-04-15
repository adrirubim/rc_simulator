from __future__ import annotations

import queue
from collections.abc import Callable


def put_with_backpressure[T](
    q: queue.Queue[T],
    item: T,
    *,
    allow_drop: bool,
    on_drop: Callable[[], None] | None = None,
    on_drop_oldest: Callable[[], None] | None = None,
) -> None:
    """
    Best-effort enqueue with bounded backpressure.

    Policy:
    - If the queue is full and `allow_drop` is True, drop the item.
    - Otherwise, drop one oldest item and retry once.
    """
    try:
        q.put_nowait(item)
        return
    except queue.Full:
        if allow_drop:
            if on_drop is not None:
                try:
                    on_drop()
                except Exception:
                    pass
            return

    # Drop one oldest and retry once.
    try:
        _ = q.get_nowait()
        if on_drop_oldest is not None:
            try:
                on_drop_oldest()
            except Exception:
                pass
    except Exception:
        if on_drop is not None:
            try:
                on_drop()
            except Exception:
                pass
        return

    try:
        q.put_nowait(item)
    except Exception:
        if on_drop is not None:
            try:
                on_drop()
            except Exception:
                pass
        return
