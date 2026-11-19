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
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusExceptionError,
)

from .transport import endpoint_key

# A Modbus TCP gateway can still misassociate late RTU replies on its serial side.
RTU_TRANSPORTS = frozenset(("serial", "rtu_tcp", "tcp_gateway"))
RTU_READ_QUIET_SECONDS = 8.0
RTU_CONSECUTIVE_TIMEOUT_LIMIT = 2


class RtuBusUnsafe(HomeAssistantError):
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
        self.expected_unload = False
        self.inflight = 0
        self.reason = None
        self.reason_at = None
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
            endpoint = endpoint_key(dict(entry.data))
            fingerprint = sha256(endpoint.encode("utf-8")).hexdigest()[:32]
            self._store = Store(hass, 1, f"comwintop.rtu_session.{fingerprint}")
        self._armed = False
        self.marker_key = self._store.key if self._store else None
        self.issue_id = f"rtu_{self.marker_key.rsplit('.', 1)[-1]}" if self._store else None

    def _issue(self, reason):
        if self._hass is None or not self.enabled:
            return
        ir.async_create_issue(
            self._hass,
            "comwintop",
            self.issue_id,
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="rtu_recovery",
            data={"marker_key": self.marker_key, "reason": reason},
            translation_placeholders={"reason": reason, "marker": self.marker_key},
        )

    def _require_clean_marker(self, saved, exists):
        if exists and saved is None:
            self._issue("corrupt_marker")
            raise ConfigEntryError(f"RTU session marker corrupt: {self.marker_key}")
        if saved not in (None, {"active": False}):
            self._issue(
                str(saved.get("reason", "unclean_restart"))
                if isinstance(saved, dict)
                else "unclean_restart"
            )
            raise ConfigEntryError(
                f"RTU session unsafe: {self.marker_key}. Use the Repairs dialog; "
                "automatic recovery is forbidden."
            )

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
        self._require_clean_marker(saved, marker_exists)
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
        self.reason_at = datetime.now(UTC).isoformat()
        self._issue(reason)
        if self._hass is not None:
            self._hass.async_create_task(
                self._store.async_save({"active": True, "reason": reason, "since": self.reason_at}),
                "ComWinTop RTU fault persistence",
            )
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

    async def manual_reset(self):
        """Only callable after all physical checks were confirmed in Repairs."""
        if not self.enabled or self.inflight:
            raise RtuBusUnsafe("RTU request still running")
        await self._store.async_save({"active": False})
        if self._hass is not None:

            def verified():
                try:
                    value = json.loads(Path(self._store.path).read_text(encoding="utf-8"))
                    return value.get("data") == {"active": False}
                except (OSError, ValueError, AttributeError):
                    return False

            if not await self._hass.async_add_executor_job(verified):
                raise RtuBusUnsafe("Cannot verify RTU marker reset")
        self._armed = False

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
