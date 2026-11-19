"""Fail-closed RTU receive safety until the shared HA backend can quarantine late frames.

A Modbus RTU reply carries no transaction ID or starting register address. An
unbounded late reply can be mistaken for another request. Therefore this gate
never claims to resynchronize an unknown bus: it blocks further integration
reads after an ambiguous exchange and survives unclean HA restarts.
"""

import asyncio
import json
import os
import time
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path

from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import Store
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusExceptionError,
)

# A Modbus TCP gateway can still misassociate late RTU replies on its serial side.
RTU_TRANSPORTS = frozenset(("serial", "rtu_tcp", "tcp_gateway"))
RTU_READ_QUIET_SECONDS = 8.0
RTU_CONSECUTIVE_TIMEOUT_LIMIT = 2


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
        self._hass = hass
        self.enabled = entry.data["transport"] in RTU_TRANSPORTS
        self.unsafe = False
        self.inflight = 0
        self.reason = None
        self.units = []
        # b17 hardware evidence: isolated missed responses (two in ~7.5 h)
        # recovered on the very next 15-second poll without sensor loss.
        # Only read-only traffic may use this bounded, best-effort recovery.
        self.consecutive_timeouts = 0
        self.transient_timeouts = 0
        self.recovered_timeouts = 0
        self.unverified_after_timeout = False
        self.quiet_until = 0.0
        # Stable per-endpoint key: removing and re-adding an integration
        # entry must not erase an unresolved bus fault. Do not expose
        # usernames, serial paths or gateway addresses in storage filenames.
        self._store = None
        if self.enabled:
            if entry.data["transport"] == "serial":
                endpoint = os.path.realpath(entry.data["device"])
            else:
                endpoint = f"{entry.data['host'].strip().lower()}:{int(entry.data['port'])}"
            fingerprint = sha256(endpoint.encode("utf-8")).hexdigest()[:32]
            self._store = Store(hass, 1, f"comwintop.rtu_session.{fingerprint}")
        self._armed = False

    async def arm(self):
        if not self.enabled:
            return
        # An existing but corrupt/unreadable marker is *not* a clean bus.
        # HA Store may return None for a malformed file.
        marker_exists = (
            await self._hass.async_add_executor_job(os.path.exists, self._store.path)
            if self._hass is not None
            else False
        )
        saved = await self._store.async_load()
        if marker_exists and saved is None:
            raise ConfigEntryError("RTU session marker corrupt; reads blocked")
        if saved not in (None, {"active": False}):
            raise ConfigEntryError(
                "Unclean or uncertain RTU session: stop competing masters, "
                "power-cycle the gateway and RTU devices, then explicitly "
                "clear the comwintop.rtu_session entry in HA storage while "
                "Home Assistant is shut down. Automatic recovery is unsafe."
            )
        # Persist before any task can transmit. Failure to persist fails setup.
        await self._store.async_save({"active": True})
        # HA's Store logs filesystem WriteError instead of propagating it.
        # Verify actual on-disk persistence before allowing *any* RTU frame.
        if hass := self._hass:

            def persisted():
                try:
                    data = json.loads(Path(self._store.path).read_text(encoding="utf-8"))
                    return data.get("key") == self._store.key and data.get("data") == {
                        "active": True
                    }
                except (OSError, ValueError, TypeError, AttributeError):
                    return False

            if not await hass.async_add_executor_job(persisted):
                raise ConfigEntryError("RTU session marker not durably stored; reads blocked")
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

    async def settle(self):
        """Keep all ComWinTop requests off the wire during a quiet period.

        This is *not* a protocol guarantee against unbounded gateway latency.
        The shared HA backend must still implement full RTU frame quarantine.
        """
        self.require_safe()
        if self.enabled:
            remaining = self.quiet_until - time.monotonic()
            if remaining > 0:
                await asyncio.sleep(remaining)
        self.require_safe()

    def _complete_read(self):
        if self.unverified_after_timeout:
            self.recovered_timeouts += 1
        self.unverified_after_timeout = False
        self.consecutive_timeouts = 0
        self.quiet_until = 0.0
        if not self.unsafe:
            self.reason = None

    @contextmanager
    def reading(self):
        """Called while holding the per-connection ComWinTop bus lock.

        A complete Modbus exception frame is a valid reply. Only the first
        isolated *read* timeout is treated as provisional loss: preserve the
        last good samples, wait for bus quiet and demand a new successful read.
        Repeated timeouts or protocol/cancellation/transport failures latch.
        Writes are never permitted by this read-only integration.
        """
        if not self.enabled:
            yield
            return
        self.require_safe()
        self.inflight += 1
        try:
            yield
        except (IllegalDataAddressError, ModbusExceptionError):
            self._complete_read()
            raise
        except TimeoutError:
            self.consecutive_timeouts += 1
            self.transient_timeouts += 1
            self.unverified_after_timeout = True
            self.reason = "transient_read_timeout"
            if self.consecutive_timeouts >= RTU_CONSECUTIVE_TIMEOUT_LIMIT:
                self.latch("repeated_read_timeout")
            else:
                self.quiet_until = time.monotonic() + RTU_READ_QUIET_SECONDS
            raise
        except (Exception, asyncio.CancelledError) as exc:
            self.latch(type(exc).__name__)
            raise
        else:
            self._complete_read()
        finally:
            self.inflight -= 1

    async def close(self):
        if not self.enabled or not self._armed:
            return
        # Task cancellation during an outstanding request latches via reading().
        if self.unsafe or self.inflight or self.unverified_after_timeout:
            return
        # Explicit clean unload allows a subsequent normal HA setup. A sudden
        # process death leaves the active marker and requires manual recovery.
        await self._store.async_save({"active": False})
        self._armed = False
