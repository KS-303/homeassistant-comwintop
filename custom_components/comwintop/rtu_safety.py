"""Fail-closed RTU receive safety until the shared HA backend can quarantine late frames.

A Modbus RTU reply carries no transaction ID or starting register address. An
unbounded late reply can be mistaken for another request. Therefore this gate
never claims to resynchronize an unknown bus: it blocks further integration
reads after an ambiguous exchange and survives unclean HA restarts.
"""

import asyncio
from contextlib import contextmanager

from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import Store
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusExceptionError,
)

RTU_TRANSPORTS = frozenset(("serial", "rtu_tcp"))


class RtuBusUnsafe(RuntimeError):
    """A previously uncertain RTU exchange requires physical bus recovery."""


class RtuSessionGuard:
    """Persist an active-session marker *before* any read on an RTU gateway.

    An unclean HA exit can interrupt a request after its frame was sent. The
    marker prevents a subsequent process from silently treating a late reply as
    a fresh one. A clean unload removes it only if no request was ambiguous.
    A fault does not automatically clear on socket reconnect or HA restart.
    """

    def __init__(self, hass, entry):
        self.enabled = entry.data["transport"] in RTU_TRANSPORTS
        self.unsafe = False
        self.inflight = 0
        self.reason = None
        self.units = []
        self._store = (
            Store(hass, 1, f"comwintop.rtu_session.{entry.entry_id}") if self.enabled else None
        )
        self._armed = False

    async def arm(self):
        if not self.enabled:
            return
        saved = await self._store.async_load()
        if saved not in (None, {"active": False}):
            raise ConfigEntryError(
                "Unclean or uncertain RTU session: stop competing masters, "
                "power-cycle the gateway and RTU devices, then explicitly "
                "clear the comwintop.rtu_session entry in HA storage while "
                "Home Assistant is shut down. Automatic recovery is unsafe."
            )
        # Persist before any task can transmit. Failure to persist fails setup.
        await self._store.async_save({"active": True})
        self._armed = True

    def attach(self, coordinator):
        self.units.append(coordinator)
        if self.unsafe:
            coordinator.mark_bus_unsafe()

    def require_safe(self):
        if self.unsafe:
            raise RtuBusUnsafe(self.reason or "rtu_bus_unsynchronized")

    def latch(self, reason):
        if not self.enabled or self.unsafe:
            return
        self.unsafe = True
        self.reason = reason
        # The on-disk active marker is intentionally not cleared on errors.
        for coordinator in self.units:
            coordinator.mark_bus_unsafe()

    @contextmanager
    def reading(self):
        """Called while holding the per-connection ComWinTop bus lock.

        A Modbus exception frame is a complete response; any other failure
        might follow a transmitted request and must latch the whole RTU bus.
        """
        if not self.enabled:
            yield
            return
        self.require_safe()
        self.inflight += 1
        try:
            yield
        except (IllegalDataAddressError, ModbusExceptionError):
            raise
        except (Exception, asyncio.CancelledError) as exc:
            self.latch(type(exc).__name__)
            raise
        finally:
            self.inflight -= 1

    async def close(self):
        if not self.enabled or not self._armed:
            return
        # Task cancellation during an outstanding request latches via reading().
        if self.unsafe or self.inflight:
            return
        # Explicit clean unload allows a subsequent normal HA setup. A sudden
        # process death leaves the active marker and requires manual recovery.
        await self._store.async_save({"active": False})
        self._armed = False
