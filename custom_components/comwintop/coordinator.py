"""Per-unit polling, per-channel quality, shared link ownership."""

import asyncio
import time
from collections import Counter
from contextlib import suppress

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from modbus_connection.exceptions import (
    ModbusConnectionError,
    ModbusExceptionError,
    ModbusProtocolError,
)

from .const import DEFAULT_INTERVALS
from .model import Sample
from .profiles import PROFILES, InvalidValue, channel_key, channels, decode_channel


class UnitCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, subentry, unit, bus_lock, logger):
        super().__init__(hass, logger, config_entry=entry, name=f"comwintop_{subentry.subentry_id}")
        self.subentry, self.unit, self.bus_lock = subentry, unit, bus_lock
        self.settings = dict(subentry.data)
        self.model = self.settings["model"]
        self.uid = self.settings["device_uid"]
        self.intervals = DEFAULT_INTERVALS | self.settings.get("intervals", {})
        self.samples = {key: Sample() for key, _, _ in channels(self.model)}
        self.counters = Counter()
        self.status = "INITIALIZING"
        self.failures = 0
        self.last_response = None
        self.latency_ms = None
        self._poll_task = None
        self._age_task = None
        self._stopping = False
        self._next = {group.kind: 0.0 for group in PROFILES[self.model]}
        # A split plan is retained on register exceptions. One request per turn,
        # with finite splitting depth, no unbounded recursive bus burst.
        self._blocks = {g.kind: [(0, g.count)] for g in PROFILES[self.model]}
        self._positions = {g.kind: 0 for g in PROFILES[self.model]}
        self._last_available = None
        self._unsubscribe = unit.on_connection_lost(self.connection_lost)
        unit.set_message_spacing(0.01)
        self.data = self.samples

    def options(self, key):
        return self.settings.get("channels", {}).get(key, {})

    def enabled(self, key):
        return self.options(key).get("enabled", True)

    def available(self, key):
        return self.enabled(key) and self.samples[key].available(
            time.monotonic(), self.intervals[key.rsplit("_", 1)[0]]
        )

    def connection_lost(self):
        if self._stopping:
            return
        self.status = "OFFLINE"
        self.counters["transport_errors"] += 1
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

    async def stop(self):
        self._stopping = True
        self._unsubscribe()
        tasks = [t for t in (self._poll_task, self._age_task) if t]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.unit.require_timeout(None)
        self.unit.require_connect_delay(None)

    async def _age(self):
        while True:
            current = tuple(self.available(key) for key in self.samples)
            if current != self._last_available:
                self._last_available = current
                self.async_set_updated_data(self.samples)
            await asyncio.sleep(0.5)

    async def _poll(self):
        groups = PROFILES[self.model]
        while True:
            now = time.monotonic()
            due = min(groups, key=lambda group: self._next[group.kind])
            if self._next[due.kind] > now:
                await asyncio.sleep(min(0.5, self._next[due.kind] - now))
                continue
            await self.poll_group(due)
            backoff = min(30, 2 ** min(self.failures, 5)) if self.failures else 1
            self._next[due.kind] = (
                time.monotonic()
                + max(0.1, self.intervals[due.kind] / len(self._blocks[due.kind])) * backoff
            )
            await asyncio.sleep(0)

    async def poll_group(self, group):
        plan = self._blocks[group.kind]
        pos = self._positions[group.kind] % len(plan)
        offset, count = plan[pos]
        self._positions[group.kind] = (pos + 1) % len(plan)
        keys = [channel_key(group.kind, i) for i in range(offset, offset + count)]
        if not any(self.enabled(key) for key in keys):
            return
        started = time.monotonic()
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
            self.failures = 0
            self.status = "ONLINE"
            self.last_response = received
            self.latency_ms = round((received - started) * 1000, 1)
            self.counters["responses"] += 1
        except ModbusExceptionError:
            self.counters["register_exceptions"] += 1
            for key in keys:
                self.samples[key].fail("register_exception", invalidate=True)
            if count > 1:
                half = count // 2
                plan[pos : pos + 1] = [(offset, half), (offset + half, count - half)]
                self._positions[group.kind] = pos
        except ModbusConnectionError:
            self.failures += 1
            self.connection_lost()
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
            # Serial late replies must not remain buffered for the next request.
            # This briefly interrupts the shared bus, not just the failed unit.
            if self.config_entry.data["transport"] in ("serial", "rtu_tcp"):
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
        self.async_set_updated_data(self.samples)

    async def _async_update_data(self):
        # Poll tasks own I/O; entity refreshes must not multiply bus requests.
        return self.samples
