"""actuate.engine.scheduler — execution-time dispatch strategy.

`SequentialScheduler` runs tasks one after another — this is the whole
of v1's scope. A `ParallelScheduler`/distributed implementation is
additive later (new capability registration, zero ExecutionEngine
changes) — see the frozen architecture, §4/§9.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


class SequentialScheduler:
    async def dispatch(self, tasks: list[Callable[[], Awaitable[Any]]]) -> list[Any]:
        results = []
        for task in tasks:
            results.append(await task())
        return results
