"""One-command-per-relay writer with bounded age and no automatic replay.

The caller must explicitly request each transition. A second command while
one is queued or executing is rejected rather than silently queued or merged.
The executor retains responsibility for guarding the actual wire boundary.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .const import WRITE_TTL
from .single_attempt import SingleAttemptUnavailable


class WriteRejected(Exception):
    """Machine-readable failure, surfaced by HA service wrappers."""


@dataclass
class Command:
    key: str
    value: int | bool
    deadline: float
    generation: int
    future: asyncio.Future
    sent: bool = False


class WriteManager:
    def __init__(
        self,
        execute: Callable[[str, int | bool, Callable[[], None]], Awaitable[int | bool]],
        allowed: Callable[[str], bool],
        *,
        clock=time.monotonic,
        ttl=WRITE_TTL,
    ):
        self.execute, self.allowed, self.clock, self.ttl = execute, allowed, clock, ttl
        self.generation = 0
        self.pending: dict[str, Command] = {}
        self.running: dict[str, Command] = {}
        self.tasks: dict[str, asyncio.Task] = {}
        self.blocked: set[str] = set()
        self.status: dict[str, str] = {}
        self.closed = False
        self.uncertain = False

    def _reject(self, command, reason):
        if not command.future.done():
            command.future.set_exception(WriteRejected(reason))
            # Retrieve for cancelled/abandoned callers; await still raises it.
            command.future.exception()

    def _check(self, key):
        if self.closed or self.uncertain or key in self.blocked or not self.allowed(key):
            raise WriteRejected("write_locked")

    async def submit(self, key, value):
        self._check(key)
        # Do not queue a later toggle behind a physical action that may have
        # already reached the relay. In particular, do not silently replay an
        # OFF after an in-flight ON. This check and insertion are atomic in
        # the HA event loop because they contain no await points.
        if key in self.pending or key in self.running or key in self.tasks:
            raise WriteRejected("write_in_progress")
        command = Command(
            key,
            value,
            self.clock() + self.ttl,
            self.generation,
            asyncio.get_running_loop().create_future(),
        )
        self.pending[key] = command
        self.tasks[key] = asyncio.create_task(self._worker(key))
        try:
            return await asyncio.shield(command.future)
        except asyncio.CancelledError:
            if self.pending.get(key) is command:
                self.pending.pop(key)
                self._reject(command, "cancelled")
            elif not command.sent:
                # Guard checks future state before any transmission.
                self._reject(command, "cancelled")
            raise

    async def _worker(self, key):
        try:
            while key in self.pending:
                command = self.pending.pop(key)
                self.running[key] = command

                def guard(command=command):
                    self._check(key)
                    if command.future.done() or command.generation != self.generation:
                        raise WriteRejected("discarded")
                    if self.clock() >= command.deadline:
                        raise WriteRejected("expired")
                    command.sent = True
                    self.status[key] = "PENDING"

                try:
                    self._check(key)
                    result = await self.execute(key, command.value, guard)
                    if not command.sent:
                        raise WriteRejected("executor_did_not_guard")
                    if result != command.value:
                        self.blocked.add(key)
                        self.status[key] = "MISMATCH"
                        if pending := self.pending.pop(key, None):
                            self._reject(pending, "channel_locked")
                        raise WriteRejected("readback_mismatch")
                    self.status[key] = "CONFIRMED"
                    if not command.future.done():
                        command.future.set_result(result)
                except WriteRejected as err:
                    if self.status.get(key) != "MISMATCH":
                        self.status[key] = "REJECTED"
                    self._reject(command, str(err))
                except SingleAttemptUnavailable:
                    # Rejection happens BEFORE the low-level frame exchange.
                    # It must not poison every output on the shared unit.
                    self.status[key] = "REJECTED"
                    self._reject(command, "transport_preflight_unavailable")
                except asyncio.CancelledError:
                    self.status[key] = "UNCONFIRMED" if command.sent else "REJECTED"
                    self._reject(command, "unloaded")
                    raise
                except Exception:
                    # Any executor uncertainty drops all queued writes for this UNIT.
                    self.communication_lost()
                    self.status[key] = "UNCONFIRMED" if command.sent else "REJECTED"
                    self._reject(command, "unconfirmed" if command.sent else "communication_error")
                finally:
                    self.running.pop(key, None)
        finally:
            self.tasks.pop(key, None)

    def communication_lost(self):
        self.generation += 1
        self.uncertain = True
        for command in self.pending.values():
            self._reject(command, "connection_generation_changed")
        self.pending.clear()

    def recovered(self):
        """Called only AFTER required fresh device/register checks, never on socket-up."""
        self.uncertain = False

    def channel_recovered(self, key):
        self.blocked.discard(key)

    def revoke(self, key):
        self.blocked.add(key)
        if pending := self.pending.pop(key, None):
            self._reject(pending, "permission_revoked")

    async def close(self):
        self.closed = True
        self.communication_lost()
        tasks = tuple(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
