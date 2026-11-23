"""Shared ComWinTop bus arbiter with writer preference and cancellation safety.

An already running Modbus exchange finishes normally. Once a write is queued,
new ComWinTop reads wait behind it; no preemption, parallel send, or retry.
All RTU frames still pass through HA's existing shared backend pacer/transport.
"""

import asyncio
from contextlib import asynccontextmanager


class PriorityBusLock:
    """One exchange at a time, with bounded write priority over new reads."""

    def __init__(self):
        self._condition = asyncio.Condition()
        self._busy = False
        self._waiting_writers = 0

    async def _acquire(self, *, writer: bool):
        async with self._condition:
            if writer:
                self._waiting_writers += 1
            try:
                await self._condition.wait_for(
                    lambda: not self._busy and (writer or self._waiting_writers == 0)
                )
                self._busy = True
            finally:
                if writer:
                    self._waiting_writers -= 1
                    # Also unblock readers if a queued writer is cancelled.
                    self._condition.notify_all()

    async def __aenter__(self):
        """Ordinary reads get the bus unless a write is already waiting."""
        await self._acquire(writer=False)
        return self

    async def __aexit__(self, *_exc):
        await self._release()

    @asynccontextmanager
    async def writer(self):
        """Prefer one pending write after the current read has finished."""
        await self._acquire(writer=True)
        try:
            yield self
        finally:
            await self._release()

    async def _release(self):
        async with self._condition:
            if not self._busy:
                raise RuntimeError("bus_lock_not_held")
            self._busy = False
            self._condition.notify_all()
