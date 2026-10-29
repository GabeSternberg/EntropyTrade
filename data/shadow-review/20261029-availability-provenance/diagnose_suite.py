"""Observe the unchanged suite's asyncio awaits without altering scheduling or assertions.

Run from the repo root under an external deadline with PYTHONASYNCIODEBUG=1.
The only extra thread emits a one-shot task dump; it never wakes or modifies an event loop.
All exchange keys used by the selected tests are generated test fixtures, not credentials.
"""

import asyncio
import gc
import inspect
import logging
import sys
import threading
from pathlib import Path

import pytest

logging.basicConfig(level=logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.DEBUG)


def dump_awaits() -> None:
    print("\nDIAGNOSTIC: pending asyncio coroutine chains", file=sys.stderr, flush=True)
    for task in (obj for obj in gc.get_objects() if isinstance(obj, asyncio.Task)):
        print(f"task={task!r}", file=sys.stderr, flush=True)
        coroutine = task.get_coro()
        seen = set()
        while coroutine is not None and id(coroutine) not in seen:
            seen.add(id(coroutine))
            if inspect.iscoroutine(coroutine):
                frame = coroutine.cr_frame
                print(
                    f"  {coroutine.__qualname__} "
                    f"{frame.f_code.co_filename if frame else ''}:"
                    f"{frame.f_lineno if frame else ''}",
                    file=sys.stderr,
                    flush=True,
                )
                coroutine = coroutine.cr_await
            else:
                print(f"  {type(coroutine).__name__}", file=sys.stderr, flush=True)
                break


timer = threading.Timer(15, dump_awaits)
timer.daemon = True
timer.start()
try:
    raise SystemExit(
        pytest.main(
            [
                "-vv",
                "-s",
                "--tb=short",
                "-o",
                "faulthandler_timeout=20",
                "--junitxml="
                + str(Path(__file__).with_name("pytest-full.xml")),
            ]
        )
    )
finally:
    timer.cancel()
