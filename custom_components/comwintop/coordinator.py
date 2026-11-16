"""Per-unit polling, per-channel quality, shared link ownership."""

import asyncio
import time
from collections import Counter, deque
from contextlib import suppress

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusExceptionError,
    ModbusProtocolError,
)

from .communication import inspect_tm32ds
from .const import DEFAULT_INTERVALS
from .model import Sample, effective_interval
from .profiles import PROFILES, InvalidValue, channel_key, channels, decode_channel


class UnitCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, subentry, unit, bus_lock, logger):
        super().__init__(hass, logger, config_entry=entry, name=f"comwintop_{subentry.subentry_id}")
        self.subentry, self.unit, self.bus_lock = subentry, unit, bus_lock
        self.settings = dict(subentry.data)
        self.model = self.settings["model"]
        self.groups = tuple(PROFILES[self.model])
        self.uid = self.settings["device_uid"]
        self.intervals = DEFAULT_INTERVALS | self.settings.get("intervals", {})
        self.samples = {key: Sample() for key, _, _ in channels(self.model)}
        self._channel_order = {key: position for position, key in enumerate(self.samples)}
        self.counters = Counter()
        self.status = "INITIALIZING"
        self.failures = 0
        self.last_response = None
        self.latency_ms = None
        self._poll_task = None
        self._age_task = None
        self._communication_task = None
        self.communication_values = None
        self.communication_received = None
        self.communication_error = None
        self._stopping = False
        self._next = {key: 0.0 if self.enabled(key) else float("inf") for key in self.samples}
        # Only a failed block is split. Its finite children are tried one at a
        # time; unrelated healthy groups retain their own deadlines.
        self._pending = deque()
        self._known_bad = set()
        self._last_available = None
        self._unsubscribe = unit.on_connection_lost(self.connection_lost)
        unit.set_message_spacing(0.01)
        self.data = self.samples

    def options(self, key):
        return self.settings.get("channels", {}).get(key, {})

    def enabled(self, key):
        return self.options(key).get("enabled", True)

    def interval(self, key):
        return effective_interval(self.settings, key)

    def available(self, key):
        return self.enabled(key) and self.samples[key].available(
            time.monotonic(), self.interval(key)
        )

    def connection_lost(self):
        if self._stopping:
            return
        self.status = "OFFLINE"
        self.counters["transport_errors"] += 1
        self.communication_values = None
        self.communication_received = None
        self.communication_error = "transport_lost"
        self._pending.clear()
        recovery_at = time.monotonic() + min(30, 2 ** min(max(self.failures, 1), 5))
        for key in self._next:
            if self.enabled(key):
                self._next[key] = recovery_at
        for sample in self.samples.values():
            sample.fail("transport_lost", invalidate=True)
        self.async_set_updated_data(self.samples)

    async def start(self):
        self._poll_task = self.config_entry.async_create_background_task(
            self.hass, self._poll(), f"comwintop_poll_{self.uid}"
        )
        self._age_task = self.config_entry.async_create_background_task(
            self.hass, self._age(), f"comwintop_age_{self.uid}"
        )
        if self.model == "tm_32ds":
            self._communication_task = self.config_entry.async_create_background_task(
                self.hass, self._communication_poll(), f"comwintop_comm_{self.uid}"
            )

    async def stop(self):
        self._stopping = True
        self._unsubscribe()
        tasks = [t for t in (self._poll_task, self._age_task, self._communication_task) if t]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.unit.require_timeout(None)
        self.unit.require_connect_delay(None)

    async def read_communication(self):
        """Refresh TM-32DS configuration via FC03 under the shared bus lock.

        This performs a read only. All parameter entities use the same cached
        register so their states agree and create no additional bus traffic.
        """
        if self.model != "tm_32ds":
            return None
        try:
            async with self.bus_lock:
                async with asyncio.timeout(3):
                    raw_values = await self.unit.read_holding_registers(16, 1)
            if len(raw_values) != 1:
                raise ValueError("invalid_communication_register_length")
            result = inspect_tm32ds(raw_values[0], self.settings["unit_id"])
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.communication_values = None
            self.communication_received = None
            self.communication_error = type(err).__name__
            self.async_set_updated_data(self.samples)
            return None
        self.communication_values = result
        self.communication_received = time.monotonic()
        self.communication_error = None
        self.async_set_updated_data(self.samples)
        return result

    async def _communication_poll(self):
        """Initial delayed read, then one shared FC03 diagnostic read every 5 min."""
        await asyncio.sleep(5)
        while True:
            await self.read_communication()
            await asyncio.sleep(300)

    async def _age(self):
        while True:
            current = tuple(self.available(key) for key in self.samples)
            if current != self._last_available:
                self._last_available = current
                self.async_set_updated_data(self.samples)
            await asyncio.sleep(0.5)

    async def _poll(self):
        while True:
            now = time.monotonic()
            next_due = min(
                (deadline for key, deadline in self._next.items() if self.enabled(key)),
                default=float("inf"),
            )
            if not self._pending and next_due > now:
                await asyncio.sleep(min(0.5, next_due - now))
                continue
            await self._poll_one(now)
            await asyncio.sleep(0)

    async def poll_group(self, group):
        """Explicit diagnostic read, also used by the pre-existing quality tests."""
        if not self._pending:
            for i in range(group.count):
                key = channel_key(group.kind, i)
                if self.enabled(key):
                    self._next[key] = 0.0
        await self._poll_one(time.monotonic(), group.kind)

    async def _poll_one(self, now, kind=None):
        if self._pending:
            group, offset, keys = self._pending.popleft()
        else:
            candidates = [
                (deadline, key)
                for key, deadline in self._next.items()
                if self.enabled(key)
                and deadline <= now
                and (kind is None or key.rsplit("_", 1)[0] == kind)
            ]
            if not candidates:
                return
            _, first = min(candidates, key=lambda item: (item[0], self._channel_order[item[1]]))
            group = next(g for g in self.groups if g.kind == first.rsplit("_", 1)[0])
            due = {key for _, key in candidates if key.startswith(f"{group.kind}_")}
            offset = int(first.rsplit("_", 1)[1]) - 1
            keys = []
            for i in range(offset, group.count):
                key = channel_key(group.kind, i)
                if key not in due or (
                    keys and (key in self._known_bad or first in self._known_bad)
                ):
                    break
                keys.append(key)
        if not keys:
            return
        count = len(keys)
        started = time.monotonic()
        split = False
        recovery = False
        try:
            # ComWinTop shares this fairness lock across its own units. The HA
            # backend also serializes ALL integrations sharing the physical link.
            async with self.bus_lock:
                async with asyncio.timeout(3):
                    values = await getattr(self.unit, group.method)(group.start + offset, count)
            if len(values) != count:
                raise ModbusProtocolError("invalid_response_length")
            received = time.monotonic()
            for key, raw in zip(keys, values, strict=True):
                if not self.enabled(key):
                    continue
                try:
                    value = decode_channel(group.kind, raw, self.options(key))
                except InvalidValue as err:
                    self.samples[key].raw = raw
                    self.samples[key].fail(str(err), invalidate=True)
                    self.samples[key].raw_received = received
                    self.counters["value_errors"] += 1
                else:
                    self.samples[key].accept(value, raw, received)
                    self._known_bad.discard(key)
            self.failures = 0
            self.status = "ONLINE"
            self.last_response = received
            self.latency_ms = round((received - started) * 1000, 1)
            self.counters["responses"] += 1
        except IllegalDataAddressError:
            self.counters["register_exceptions"] += 1
            if count > 1:
                half = count // 2
                # Exactly count-1 additional requests in the worst case.
                self._pending.appendleft((group, offset + half, keys[half:]))
                self._pending.appendleft((group, offset, keys[:half]))
                split = True
            else:
                self.samples[keys[0]].fail("register_exception", invalidate=True)
                self._known_bad.add(keys[0])
        except ModbusExceptionError:
            # Busy and other exceptions are not evidence of a bad register.
            # Never fan a 32-register block out into 63 busy retries.
            self.failures += 1
            self.status = "SUSPECT" if self.failures < 3 else "OFFLINE"
            self.counters["device_exceptions"] += 1
            for key in keys:
                self.samples[key].fail("device_exception", invalidate=self.failures >= 3)
        except ModbusConnectionError:
            self.failures += 1
            self.connection_lost()
            recovery = True
        except (TimeoutError, ModbusProtocolError) as err:
            self.failures += 1
            code = "timeout" if isinstance(err, TimeoutError) else "protocol_error"
            self.counters[code] += 1
            self.status = "OFFLINE" if self.failures >= 3 else "SUSPECT"
            for key in keys:
                self.samples[key].fail(code)
            if self.failures >= 3:
                for sample in self.samples.values():
                    sample.fail("unit_offline", invalidate=True)
                recovery_at = time.monotonic() + min(30, 2 ** min(self.failures, 5))
                for key in self._next:
                    if self.enabled(key):
                        self._next[key] = recovery_at
                recovery = True
            # Serial late replies must not remain buffered for the next request.
            # This briefly interrupts the shared bus, not just the failed unit.
            if self.config_entry.data["transport"] in ("serial", "rtu_tcp"):
                # Never close the shared transport while another unit is
                # actively exchanging a frame on the same ComWinTop bus.
                async with self.bus_lock:
                    with suppress(ModbusConnectionError):
                        await self.unit.disconnect()
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception as err:
            # Keep diagnostics useful without exposing IPs/payloads in messages.
            self.counters["unexpected_errors"] += 1
            self.status = "SUSPECT"
            for key in keys:
                self.samples[key].fail(type(err).__name__)
        if not split and not recovery:
            completed = time.monotonic()
            for key in keys:
                # Bound the *absolute* delay after a device exception to 30 s.
                # A Busy reply on a slow polling channel must not schedule
                # hundreds of seconds of unavailability.
                retry_delay = (
                    min(30, self.interval(key) * 2 ** min(self.failures, 5))
                    if self.failures
                    else self.interval(key)
                )
                self._next[key] = completed + retry_delay
        self.async_set_updated_data(self.samples)

    async def _async_update_data(self):
        # Poll tasks own I/O; entity refreshes must not multiply bus requests.
        return self.samples
