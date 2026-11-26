"""Per-unit polling, per-channel quality, shared link ownership."""

import asyncio
import time
from collections import Counter, deque
from contextlib import suppress
from datetime import UTC, datetime

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from modbus_connection.exceptions import (
    IllegalDataAddressError,
    ModbusConnectionError,
    ModbusExceptionError,
    ModbusProtocolError,
)

from .communication import inspect_tm32ds
from .const import (
    BUS_MESSAGE_SPACING,
    DEFAULT_INTERVALS,
    HARDWARE_VALIDATED_WRITES,
    READ_DEADLINE,
)
from .model import Sample, effective_interval
from .profiles import PROFILES, InvalidValue, channel_key, channels, decode_channel
from .recovery import RecoveryStore, recovery_targets
from .single_attempt import SingleAttemptUnavailable, fc05_once
from .write_manager import WriteManager, WriteRejected


def failed_poll_delay(interval: float, failures: int) -> float:
    """Back off transient read failures without accelerating slow channels."""
    if failures <= 1:
        # One missed reply must not double a healthy channel cadence:
        # 15 s + 3 s timeout + 30 s retry would exceed its 45 s stale limit.
        return interval
    return min(max(30, interval), interval * 2 ** min(failures - 1, 5))


class UnitCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, subentry, unit, bus_lock, logger, rtu_guard=None):
        super().__init__(hass, logger, config_entry=entry, name=f"comwintop_{subentry.subentry_id}")
        self.subentry, self.unit, self.bus_lock = subentry, unit, bus_lock
        self.rtu_guard = rtu_guard
        self._logger = logger
        self.settings = dict(subentry.data)
        self.model = self.settings["model"]
        self.groups = tuple(PROFILES[self.model])
        self.uid = self.settings["device_uid"]
        self.intervals = DEFAULT_INTERVALS | self.settings.get("intervals", {})
        self.samples = {key: Sample() for key, _, _ in channels(self.model)}
        self._channel_order = {key: position for position, key in enumerate(self.samples)}
        self.counters = Counter()
        # Bounded, in-memory history (no addresses of gateways or sensor values).
        self._timeout_history = deque(maxlen=64)
        self.status = (
            "INITIALIZING" if any(self.enabled(key) for key in self.samples) else "INACTIVE"
        )
        self.failures = 0
        self.last_response = None
        self.latency_ms = None
        self.bus_lock_wait_ms = None
        self.read_call_ms = None
        self._poll_task = None
        self._age_task = None
        self._communication_task = None
        self.communication_values = None
        self.communication_received = None
        self.communication_error = None
        self._communication_refresh = asyncio.Event()
        self._communication_retry_at = 0.0
        self._stopping = False
        self.last_write_phase = None
        self.last_write_duration_ms = None
        self.last_write_error = None
        self._next = {key: 0.0 if self.enabled(key) else float("inf") for key in self.samples}
        # Only a failed block is split. Its finite children are tried one at a
        # time; unrelated healthy groups retain their own deadlines.
        self._pending = deque()
        self._known_bad = set()
        self._last_available = None
        minimum_read_rate = 0.0
        for group in self.groups:
            intervals = [
                self.interval(key)
                for i in range(group.count)
                if self.enabled(key := channel_key(group.kind, i))
            ]
            if intervals:
                minimum_read_rate += 1 / min(intervals)
        self.minimum_read_rate_hz = round(minimum_read_rate, 3)
        if minimum_read_rate * BUS_MESSAGE_SPACING >= 0.9:
            logger.warning(
                "ComWinTop minimum read load approaches shared bus capacity; "
                "increase configured intervals or reduce active channels"
            )
        # Register the listener last so a rejected unit setting cannot leak
        # a live callback from a partially constructed coordinator.
        # Public modbus-connection pacer serializes the physical link, including
        # other units on the same HA connection. Starts after the last exchange.
        unit.set_message_spacing(BUS_MESSAGE_SPACING)
        self._unsubscribe = unit.on_connection_lost(self.connection_lost)
        # A validated on-wire transport gate is mandatory. The current
        # unpatched HA backend does not meet this requirement. Merely
        # enabling a channel in the UI cannot activate writing.
        self._write_manager = (
            WriteManager(self._execute_do, self._can_write)
            if (self.model, entry.data["transport"], "fc05") in HARDWARE_VALIDATED_WRITES
            else None
        )
        self.data = self.samples
        self._recovery_store = (
            RecoveryStore(hass, entry, subentry) if self._write_manager is not None else None
        )
        self._recovery_pending = False
        self._recovery_failed = False
        self._recovery_since = 0.0
        self._recovery_misses = 0
        self._recovery_done = set()
        self.recovery_phase = "idle"
        self.recovery_at = None

    def _can_write(self, key, *, recovery=False):
        """Permissions and fresh state are checked again at transmit time."""
        return (
            self.model == "mb_307d_ii_s"
            and key.startswith("do_")
            and key in self.samples
            and self.enabled(key)
            and self.options(key).get("write_enabled", False) is True
            and self.available(key)
            and self.status == "ONLINE"
            and not self._stopping
            and (recovery or not getattr(self, "_recovery_pending", False))
            and (
                self.rtu_guard is None
                or (
                    not self.rtu_guard.unsafe
                    and not getattr(self.rtu_guard, "unverified_after_timeout", False)
                )
            )
        )

    def _recovery_targets(self):
        return recovery_targets(self.config_entry.data, self.settings)

    async def prepare_recovery(self):
        """Load durable intent before polling or exposing controls."""
        if self._recovery_store is None:
            return
        if await self._recovery_store.load():
            if self._recovery_targets():
                self._recovery_pending = True
                self._recovery_since = time.monotonic()
                self.recovery_phase = "pending"
                self.recovery_at = datetime.now(UTC).isoformat()
                self._write_manager.communication_lost()
            else:
                await self._recovery_store.save(False)

    async def _mark_output_recovery(self):
        if self._recovery_store is None or not self._recovery_targets():
            return
        if self._recovery_pending:
            return
        self._recovery_pending = True
        self._recovery_done.clear()
        self._recovery_since = time.monotonic()
        self.recovery_phase = "pending"
        self.recovery_at = datetime.now(UTC).isoformat()
        self._write_manager.communication_lost()
        self.async_set_updated_data(self.samples)
        try:
            await self._recovery_store.save(True)
        except Exception:
            self._recovery_failed = True
            self.recovery_phase = "storage_error"
            self.rtu_guard.latch("relay_recovery_storage_error")
            raise
        for key in self._recovery_targets():
            self._next[key] = 0.0

    def _fail_output_recovery(self, reason):
        self._recovery_failed = True
        self.recovery_phase = "failed"
        self.recovery_at = datetime.now(UTC).isoformat()
        self.counters["relay_recovery_failed"] += 1
        self._logger.error("ComWinTop relay recovery failed: %s", reason)
        self.rtu_guard.latch("relay_recovery_failed")
        self.async_set_updated_data(self.samples)

    async def _maybe_recover_outputs(self):
        """Check one target per poll turn; never replay an old command."""
        if not self._recovery_pending or self._recovery_failed:
            return
        # A permanently invalid register must not leave the write lock
        # pending forever. Physical repair is required after this deadline.
        if time.monotonic() - self._recovery_since >= 120:
            self._fail_output_recovery("recovery_deadline")
            return
        manager = self._write_manager
        if manager is None or manager.closed or manager.tasks:
            return
        targets = self._recovery_targets()
        if not targets or self.status != "ONLINE":
            return
        remaining = {key: value for key, value in targets.items() if key not in self._recovery_done}
        # Poll normally between individual writes so short poll intervals
        # remain usable even when all eight relays need to be reset.
        for key, value in remaining.items():
            sample = self.samples[key]
            if (
                not self._can_write(key, recovery=True)
                or sample.received is None
                or sample.received < self._recovery_since
                or type(sample.value) is not bool
            ):
                continue
            generation = manager.generation
            self.recovery_phase = "applying"
            try:

                def guard(key=key):
                    if (
                        not self._recovery_pending
                        or self._recovery_failed
                        or manager.generation != generation
                        or manager.closed
                        or manager.tasks
                        or key in manager.blocked
                        or not self._can_write(key, recovery=True)
                        or time.monotonic() - self._recovery_since >= 120
                    ):
                        raise WriteRejected("recovery_preflight_rejected")

                guard()
                if sample.value is not value:
                    if await self._execute_do(key, value, guard) is not value:
                        raise WriteRejected("recovery_readback_mismatch")
                if manager.generation != generation or self.rtu_guard.unsafe:
                    raise WriteRejected("recovery_generation_changed")
                self._recovery_done.add(key)
                if self._recovery_done == set(targets):
                    await self._recovery_store.save(False)
                    if manager.generation != generation or self.rtu_guard.unsafe:
                        raise WriteRejected("recovery_generation_changed")
                    self._recovery_pending = False
                    self.recovery_phase = "confirmed"
                    self.recovery_at = datetime.now(UTC).isoformat()
                    self.counters["relay_recovery_completed"] += 1
                    manager.recovered()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self._fail_output_recovery(type(err).__name__)
            self.async_set_updated_data(self.samples)
            return

    async def _execute_do(self, key, value, guard):
        """One FC05 request and one FC01 readback, no duplicate write attempts."""
        address = int(key.removeprefix("do_")) - 1
        started = time.monotonic()
        phase = "waiting_for_bus"
        self.last_write_phase = phase
        self.last_write_duration_ms = None
        self.last_write_error = None
        try:
            async with self.bus_lock.writer():
                if self.rtu_guard is not None:
                    await self.rtu_guard.settle()
                phase = "fc05_preflight"
                self.last_write_phase = phase
                # This may reject BEFORE any frame is sent. Those failures
                # must NEVER latch the physical RTU bus as unsynchronized.
                await fc05_once(self.unit, address, bool(value), guard)
                phase = "fc01_readback"
                self.last_write_phase = phase
                # HA's existing four-second read deadline already includes
                # the one-second spacing. Avoid artificially adding delay.
                async with asyncio.timeout(READ_DEADLINE):
                    readback = await self.unit.read_coils(address, 1)
                if len(readback) != 1 or type(readback[0]) is not bool:
                    raise ModbusProtocolError("invalid_do_readback")
                # FC01 returned a genuine state from this slave. Publish it
                # immediately instead of waiting up to the normal DO poll
                # interval. It is a coil readback, NOT physical contact proof.
                received = time.monotonic()
                self.samples[key].accept(readback[0], readback[0], received)
                self.last_response = received
                self._refresh_read_status()
                self.async_set_updated_data(self.samples)
                phase = "confirmed"
                self.last_write_phase = phase
                return readback[0]
        except (WriteRejected, SingleAttemptUnavailable) as err:
            # Both types are raised only at the pre-transmit guard/boundary.
            # A refused/stale/expired permission is NOT a hardware fault.
            self.last_write_phase = "rejected_before_send"
            self.last_write_error = type(err).__name__
            raise
        except (Exception, asyncio.CancelledError) as err:
            self.last_write_phase = phase
            self.last_write_error = type(err).__name__
            # Waiting for the hub's own lock cannot have sent an FC05.
            # Once the FC05 boundary is entered, a failure may be a
            # physically completed but unconfirmed relay change.
            if phase != "waiting_for_bus" and self.rtu_guard is not None:
                self.rtu_guard.latch(
                    "write_readback_unconfirmed"
                    if phase == "fc01_readback"
                    else "write_fc05_unconfirmed"
                )
            raise
        finally:
            self.last_write_duration_ms = round((time.monotonic() - started) * 1000, 1)
            self.async_set_updated_data(self.samples)

    async def async_set_output(self, key, value):
        """Fail closed unless a backend is independently certified."""
        from homeassistant.exceptions import HomeAssistantError

        if self._write_manager is None:
            raise HomeAssistantError("Schreiben ist für diesen Modbus-Transport gesperrt.")
        try:
            return await self._write_manager.submit(key, value)
        except WriteRejected as err:
            german = self.hass.config.language.lower().startswith("de")
            messages = {
                "write_in_progress": (
                    "Schaltvorgang läuft bereits. Bitte erst die Rückmeldung abwarten.",
                    "Relay command in progress. Wait for readback confirmation.",
                ),
                "expired": (
                    "Schaltauftrag abgelaufen, bevor er gesendet werden konnte.",
                    "Relay command expired before transmission.",
                ),
                "write_locked": (
                    "Schalten derzeit gesperrt. Freigabe und Rückmeldung prüfen.",
                    "Switching is locked. Check permission and readback.",
                ),
                "readback_mismatch": (
                    "Schaltzustand stimmt nicht mit der Rückmeldung überein.",
                    "Relay state does not match readback.",
                ),
                "unconfirmed": (
                    "Schaltbefehl nicht sicher bestätigt. Relaiszustand prüfen.",
                    "Relay command unconfirmed. Check physical relay state.",
                ),
                "transport_preflight_unavailable": (
                    "Schalttransport nicht bereit. Kein Telegramm gesendet.",
                    "Write transport unavailable. No frame sent.",
                ),
            }
            de, en = messages.get(
                str(err),
                (
                    "Schaltauftrag abgelehnt. Status und Diagnose prüfen.",
                    "Relay command rejected. Check status and diagnostics.",
                ),
            )
            raise HomeAssistantError(de if german else en) from err

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

    def _refresh_read_status(self):
        """Report data quality without flashing SUSPECT after one recovered-capable miss.

        An RTU uncertainty stays enforced by its independent fail-closed guard.
        A fresh previous reply can keep the status ONLINE for a single miss,
        but unavailable/stale samples or repeated failures are never hidden.
        """
        active = [(key, self.samples[key]) for key in self.samples if self.enabled(key)]
        if not active:
            self.status = "INACTIVE"
        elif self.rtu_guard is not None and self.rtu_guard.unsafe:
            self.status = "OFFLINE"
        elif self.counters["poll_task_exhausted"] or any(
            sample.error == "poll_task_failed" for _, sample in active
        ):
            self.status = "OFFLINE"
        elif all(sample.consecutive_read_failures >= 3 for _, sample in active):
            self.status = "OFFLINE"
        elif any(sample.consecutive_read_failures >= 3 for _, sample in active):
            self.status = "SUSPECT"
        elif any(
            (
                last_reply := (
                    sample.raw_received if sample.raw_received is not None else sample.received
                )
            )
            is not None
            and sample.error != "register_exception"
            and time.monotonic() - last_reply >= 3 * self.interval(key)
            for key, sample in active
        ):
            self.status = "SUSPECT"
        elif self.last_response is not None or any(
            sample.received is not None for _, sample in active
        ):
            self.status = "ONLINE"
        elif any(sample.consecutive_read_failures for _, sample in active):
            self.status = "SUSPECT"
        else:
            self.status = "INITIALIZING"

    def record_timeout(self, group, start, count):
        """Keep a bounded history of actual failed Modbus read attempts."""
        event = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "modbus_address": int(self.settings["unit_id"]),
            "register_group": group,
            "start_register": start,
            "register_count": count,
            "error": "timeout",
            "recovered_at_utc": None,
            "recovery_seconds": None,
            "state": (
                "bus_latched" if self.rtu_guard is not None and self.rtu_guard.unsafe else "pending"
            ),
            "_started_monotonic": time.monotonic(),
        }
        self._timeout_history.append(event)

    def complete_timeouts(self, group, start, count):
        """Only a matching successful read confirms recovery of a failed range."""
        now = time.monotonic()
        for event in self._timeout_history:
            if (
                event["state"] == "pending"
                and event["register_group"] == group
                and start <= event["start_register"]
                and start + count >= event["start_register"] + event["register_count"]
            ):
                event["state"] = "recovered"
                event["recovery_seconds"] = round(now - event["_started_monotonic"], 3)
                event["recovered_at_utc"] = datetime.now(UTC).isoformat()

    def latch_timeout_history(self):
        """A latched bus is not a recovered bus."""
        for event in self._timeout_history:
            if event["state"] == "pending":
                event["state"] = "bus_latched"

    @property
    def timeout_history(self):
        """Public diagnostics omit private monotonic bookkeeping."""
        return [
            {key: value for key, value in event.items() if not key.startswith("_")}
            for event in self._timeout_history
        ]

    def mark_bus_unsafe(self):
        if self._write_manager is not None:
            self._write_manager.communication_lost()
        """Invalidate readings immediately; do not claim an RTU response is fresh."""
        self.latch_timeout_history()
        self.status = "OFFLINE"
        self.communication_values = None
        self.communication_received = None
        self.communication_error = "rtu_bus_unsynchronized"
        self._pending.clear()
        for sample in self.samples.values():
            sample.fail("rtu_bus_unsynchronized", invalidate=True)
        for key in self._next:
            self._next[key] = float("inf")
        self.async_set_updated_data(self.samples)

    def connection_lost(self):
        if self._write_manager is not None:
            self._write_manager.communication_lost()
        if self._stopping:
            return
        if self.rtu_guard is not None and self.rtu_guard.enabled:
            if self.rtu_guard.expected_unload and self.rtu_guard.inflight == 0:
                # Unloading the HA platforms may briefly close the shared
                # connection before coordinators finish their stop calls.
                return
            self.rtu_guard.latch("transport_lost")
            return
        self.status = "OFFLINE" if any(self.enabled(key) for key in self.samples) else "INACTIVE"
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
            sample.consecutive_read_failures = max(3, sample.consecutive_read_failures)
        self.async_set_updated_data(self.samples)

    async def start(self):
        self._poll_task = self.config_entry.async_create_background_task(
            self.hass, self._poll_supervised(), f"comwintop_poll_{self.uid}"
        )
        self._age_task = self.config_entry.async_create_background_task(
            self.hass, self._age(), f"comwintop_age_{self.uid}"
        )
        if self.model == "tm_32ds":
            self._communication_task = self.config_entry.async_create_background_task(
                self.hass, self._communication_poll(), f"comwintop_comm_{self.uid}"
            )

    @property
    def poll_running(self):
        return bool(self._poll_task and not self._poll_task.done())

    async def stop(self):
        if self._stopping:
            return
        self._stopping = True
        if self._write_manager is not None:
            await self._write_manager.close()
        self._unsubscribe()
        tasks = [t for t in (self._poll_task, self._age_task, self._communication_task) if t]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.unit.require_timeout(None)
        self.unit.require_connect_delay(None)
        self.unit.set_message_spacing(0)

    async def read_communication(self):
        """Refresh TM-32DS configuration via FC03 under the shared bus lock.

        This performs a read only. All parameter entities use the same cached
        register so their states agree and create no additional bus traffic.
        """
        if self.model != "tm_32ds":
            return None
        try:
            async with self.bus_lock:
                if self.rtu_guard is not None:
                    await self.rtu_guard.settle()
                if self.rtu_guard is None:
                    async with asyncio.timeout(READ_DEADLINE):
                        raw_values = await self.unit.read_holding_registers(16, 1)
                else:
                    with self.rtu_guard.reading():
                        async with asyncio.timeout(READ_DEADLINE):
                            raw_values = await self.unit.read_holding_registers(16, 1)
            if len(raw_values) != 1:
                if self.rtu_guard is not None:
                    self.rtu_guard.latch("invalid_communication_register_length")
                raise ValueError("invalid_communication_register_length")
            result = inspect_tm32ds(raw_values[0], self.settings["unit_id"])
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self.communication_values = None
            self.communication_received = None
            self.communication_error = type(err).__name__
            self._communication_retry_at = time.monotonic() + 30
            if isinstance(err, TimeoutError):
                self.record_timeout("communication", 16, 1)
            self.async_set_updated_data(self.samples)
            return None
        self.complete_timeouts("communication", 16, 1)
        self.communication_values = result
        self.communication_received = time.monotonic()
        self.communication_error = None
        self._communication_retry_at = 0.0
        self.async_set_updated_data(self.samples)
        return result

    async def _communication_poll(self):
        """Initial delayed read, then one shared FC03 diagnostic read every 5 min."""
        await asyncio.sleep(5)
        while True:
            if self.rtu_guard is not None and self.rtu_guard.unsafe:
                return
            # Clear before reading: an event raised while the request is in
            # flight must be observed by the next loop, not silently lost.
            self._communication_refresh.clear()
            await self.read_communication()
            try:
                async with asyncio.timeout(300):
                    await self._communication_refresh.wait()
            except TimeoutError:
                pass

    async def _age(self):
        while True:
            current = tuple(self.available(key) for key in self.samples)
            previous_status = self.status
            self._refresh_read_status()
            if current != self._last_available or self.status != previous_status:
                self._last_available = current
                self.async_set_updated_data(self.samples)
            await asyncio.sleep(0.5)

    async def _poll_supervised(self):
        """Restart an unexpected poll-loop crash, at most twice in five minutes."""
        crashes = deque()
        while not self._stopping:
            try:
                await self._poll()
                raise RuntimeError("poll_loop_returned")
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self._logger.error("ComWinTop polling stopped: %s", type(err).__name__)
                self.counters["poll_task_failures"] += 1
                self.status = "OFFLINE"
                self._pending.clear()
                for sample in self.samples.values():
                    sample.fail("poll_task_failed", invalidate=True)
                self.async_set_updated_data(self.samples)
                now = time.monotonic()
                while crashes and now - crashes[0] > 300:
                    crashes.popleft()
                crashes.append(now)
                if len(crashes) >= 3:
                    self.counters["poll_task_exhausted"] += 1
                    ir.async_create_issue(
                        self.hass,
                        "comwintop",
                        f"poll_exhausted_{self.uid}",
                        is_fixable=False,
                        is_persistent=True,
                        severity=ir.IssueSeverity.ERROR,
                        translation_key="poll_exhausted",
                    )
                    self._logger.critical("ComWinTop polling exhausted its restart budget")
                    self.async_set_updated_data(self.samples)
                    return
                await asyncio.sleep(2 ** len(crashes))
                for key in self._next:
                    if self.enabled(key):
                        self._next[key] = 0.0

    async def _poll(self):
        while True:
            if self.rtu_guard is not None and self.rtu_guard.unsafe:
                await asyncio.sleep(1)
                continue
            await self._maybe_recover_outputs()
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
        if self.rtu_guard is not None and self.rtu_guard.unsafe:
            return
        count = len(keys)
        split = False
        recovery = False
        self.read_call_ms = None
        waiting_since = time.monotonic()
        try:
            # ComWinTop shares this fairness lock across its own units. The HA
            # backend also serializes ALL integrations sharing the physical link.
            async with self.bus_lock:
                if self.rtu_guard is not None:
                    await self.rtu_guard.settle()
                acquired = time.monotonic()
                self.bus_lock_wait_ms = round((acquired - waiting_since) * 1000, 1)
                if self.rtu_guard is None:
                    async with asyncio.timeout(READ_DEADLINE):
                        called = time.monotonic()
                        values = await getattr(self.unit, group.method)(group.start + offset, count)
                        self.read_call_ms = round((time.monotonic() - called) * 1000, 1)
                else:
                    with self.rtu_guard.reading():
                        async with asyncio.timeout(READ_DEADLINE):
                            called = time.monotonic()
                            values = await getattr(self.unit, group.method)(
                                group.start + offset, count
                            )
                            self.read_call_ms = round((time.monotonic() - called) * 1000, 1)
            if len(values) != count:
                raise ModbusProtocolError("invalid_response_length")
            received = time.monotonic()
            for key, raw in zip(keys, values, strict=True):
                if not self.enabled(key):
                    continue
                # A valid Modbus reply proves that this channel's *communication*
                # succeeded even when the physical probe reports an invalid value.
                self.samples[key].consecutive_read_failures = 0
                try:
                    value = decode_channel(group.kind, raw, self.options(key), model=self.model)
                except InvalidValue as err:
                    self.samples[key].invalid_value(str(err), raw, received)
                    self.counters["value_errors"] += 1
                else:
                    self.samples[key].accept(value, raw, received)
                    self._known_bad.discard(key)
            self.complete_timeouts(group.kind, group.start + offset, count)
            self._recovery_misses = 0
            self.failures = 0
            self.last_response = received
            self._refresh_read_status()
            # The public HA Modbus API does not expose a wire-send timestamp.
            # A call may include pacer and backend queue time: do not report it
            # as device latency. Keep the legacy field empty for consumers.
            self.latency_ms = None
            self.counters["responses"] += 1
            if (
                self.model == "tm_32ds"
                and self.communication_values is None
                and received >= self._communication_retry_at
            ):
                # A fresh temperature reply proves the link recovered. Refresh
                # the cached communication register once through the same bus.
                self._communication_refresh.set()
        except IllegalDataAddressError:
            self._recovery_misses = 0
            self.counters["register_exceptions"] += 1
            if count > 1:
                half = count // 2
                # Exactly count-1 additional requests in the worst case.
                self._pending.appendleft((group, offset + half, keys[half:]))
                self._pending.appendleft((group, offset, keys[:half]))
                split = True
            else:
                sample = self.samples[keys[0]]
                # Exception 02 is a complete response from this slave, even
                # though this individual register has no usable value.
                sample.consecutive_read_failures = 0
                sample.fail("register_exception", invalidate=True)
                self._known_bad.add(keys[0])
                self.failures = 0
                self.last_response = time.monotonic()
                self._refresh_read_status()
        except ModbusExceptionError:
            self._recovery_misses = 0
            # Busy and other exceptions are not evidence of a bad register.
            # Never fan a 32-register block out into 63 busy retries.
            self.failures += 1
            self.counters["device_exceptions"] += 1
            for key in keys:
                self.samples[key].read_failed("device_exception")
            self._refresh_read_status()
        except ModbusConnectionError:
            self.failures += 1
            self.connection_lost()
            recovery = True
        except (TimeoutError, ModbusProtocolError) as err:
            self.failures += 1
            code = "timeout" if isinstance(err, TimeoutError) else "protocol_error"
            if code == "protocol_error" and self.rtu_guard is not None:
                self.rtu_guard.latch("protocol_error")
            self.counters[code] += 1
            if code == "timeout":
                self.record_timeout(group.kind, group.start + offset, count)
                self._recovery_misses = getattr(self, "_recovery_misses", 0) + 1
                if (
                    self._recovery_misses >= 3
                    and getattr(self, "_recovery_store", None) is not None
                    and not self.rtu_guard.unsafe
                ):
                    await self._mark_output_recovery()
            for key in keys:
                self.samples[key].read_failed(code)
            self._refresh_read_status()
            # A single provisional RTU timeout is tracked by the guard,
            # not misrepresented as a persistent communication outage.
            if self.status == "OFFLINE":
                recovery_at = time.monotonic() + min(30, 2 ** min(self.failures, 5))
                for key in self._next:
                    if self.enabled(key):
                        self._next[key] = recovery_at
                recovery = True
            # Serial late replies must not remain buffered for the next request.
            # This briefly interrupts the shared bus, not just the failed unit.
            if self.config_entry.data["transport"] in ("serial", "rtu_tcp"):
                # b17 showed isolated unanswered reads with immediate recovery.
                # Closing the shared transport after the first read timeout
                # could defeat the provisional recovery path via connection_lost.
                # The guarded read-only path instead pauses before any new
                # ComWinTop request. A second timeout or protocol failure
                # latches the bus and no further reads will be attempted.
                provisional = (
                    self.rtu_guard is not None
                    and self.rtu_guard.unverified_after_timeout
                    and not self.rtu_guard.unsafe
                )
                if not provisional:
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
        if self.rtu_guard is not None and self.rtu_guard.unsafe:
            # The specific exception handler must not turn a latched RTU
            # fault back into SUSPECT/ONLINE or re-arm channel deadlines.
            self.mark_bus_unsafe()
            return
        if not split and not recovery:
            completed = time.monotonic()
            for key in keys:
                # Never retry more frequently than the configured channel
                # interval. The 30-second cap only applies to short intervals.
                retry_delay = failed_poll_delay(self.interval(key), self.failures)
                self._next[key] = completed + retry_delay
        self.async_set_updated_data(self.samples)

    async def _async_update_data(self):
        # Poll tasks own I/O; entity refreshes must not multiply bus requests.
        return self.samples
