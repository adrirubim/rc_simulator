from __future__ import annotations

import queue


def drain_queue[T](q: queue.Queue[T], *, max_items: int) -> list[T]:
    if max_items <= 0:
        return []
    out: list[T] = []
    for _ in range(max_items):
        try:
            out.append(q.get_nowait())
        except queue.Empty:
            break
    return out
