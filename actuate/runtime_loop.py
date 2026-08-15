"""Windows asyncio: psycopg cannot run on ProactorEventLoop.

Uvicorn 0.36+ *returns ProactorEventLoop as its loop factory on Windows*,
which ignores asyncio.set_event_loop_policy. The API must pass this
factory into uvicorn.run(loop_factory=...).
"""

from __future__ import annotations

import asyncio
import selectors
import sys
from collections.abc import Callable


def configure_windows_selector_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def selector_loop_factory() -> Callable[[], asyncio.AbstractEventLoop]:
    def factory() -> asyncio.AbstractEventLoop:
        if sys.platform == "win32":
            return asyncio.SelectorEventLoop(selectors.SelectSelector())
        return asyncio.new_event_loop()

    return factory
