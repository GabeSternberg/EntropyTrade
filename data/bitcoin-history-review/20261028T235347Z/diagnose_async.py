"""Bounded wakeup diagnostic. No monkeypatching, credentials or network endpoints."""

import asyncio
import json
import logging
import socket
import time

logging.basicConfig(level=logging.DEBUG)
reader, writer = socket.socketpair()
try:
    writer.send(b"x")
    print(json.dumps({"socketpair_send": "passed", "read": reader.recv(1).decode()}), flush=True)
except PermissionError as exc:
    print(json.dumps({"socketpair_send": str(exc)}), flush=True)
finally:
    reader.close()
    writer.close()

loop = asyncio.new_event_loop()
loop.set_debug(True)
started = time.monotonic()
try:
    # A timer bounds the otherwise lost cross-thread wakeup. The executor work is 50ms.
    loop.run_until_complete(asyncio.wait_for(asyncio.to_thread(time.sleep, 0.05), timeout=1))
    print(json.dumps({"executor_seconds": time.monotonic() - started}), flush=True)
finally:
    loop.close()
