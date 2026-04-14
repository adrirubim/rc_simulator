from __future__ import annotations

import queue

from rc_simulator.ui_qt.views._queue_drain import drain_queue


def test_drain_queue_limits_items() -> None:
    q: queue.Queue[int] = queue.Queue()
    for i in range(100):
        q.put(i)

    drained = drain_queue(q, max_items=10)
    assert drained == list(range(10))
    assert q.qsize() == 90
