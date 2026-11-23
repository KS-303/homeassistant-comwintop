"""Pure, deterministic quality and configuration rules."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime

from .const import CONFIGURABLE_MIN_INTERVALS, DEFAULT_INTERVALS, MIN_INTERVALS, STALE_FACTOR
from .profiles import MODES, InvalidValue, channels, finite


def effective_interval(data, key):
    """Legacy entries without a channel override inherit their group interval."""
    kind = key.rsplit("_", 1)[0]
    override = data.get("channels", {}).get(key, {}).get("poll_interval")
    return (
        override
        if override is not None
        else data.get("intervals", {}).get(kind, DEFAULT_INTERVALS[kind])
    )


@dataclass
class Sample:
    value: float | bool | None = None
    raw: int | bool | None = None
    received: float | None = None
    raw_received: float | None = None
    error: str | None = None
    invalid: bool = False
    successful_reads: int = 0
    consecutive_read_failures: int = 0
    consecutive_invalid_values: int = 0
    consecutive_probe_fault_values: int = 0
    last_successful_read_utc: str | None = None
    last_successful_read_delta_seconds: float | None = None

    def available(self, now, interval):
        return (
            self.received is not None
            and not self.invalid
            and now - self.received < STALE_FACTOR * interval
        )

    def accept(self, value, raw, now):
        if self.received is not None:
            self.last_successful_read_delta_seconds = round(now - self.received, 3)
        self.value, self.raw, self.received = value, raw, now
        self.successful_reads += 1
        self.last_successful_read_utc = datetime.now(UTC).isoformat()
        self.raw_received = now
        self.error, self.invalid = None, False
        self.consecutive_read_failures = 0
        self.consecutive_invalid_values = 0
        self.consecutive_probe_fault_values = 0

    def invalid_value(self, error, raw, now):
        """A complete device reply with an invalid *individual* channel value."""
        self.consecutive_read_failures = 0
        self.consecutive_invalid_values += 1
        # Only the measured TM-32DS unplugged-DS18B20 sentinel proves this
        # particular fault. 85 °C and unknown encodings are ambiguous.
        self.consecutive_probe_fault_values = (
            self.consecutive_probe_fault_values + 1 if raw == 0xFC18 else 0
        )
        self.raw, self.raw_received = raw, now
        self.fail(error, invalidate=True)
        # The raw diagnostic must remain visible after a valid Modbus reply.
        self.raw_received = now

    def read_failed(self, error):
        """Record a failed request for this channel, independently of its peers."""
        self.consecutive_read_failures += 1
        self.fail(error, invalidate=self.consecutive_read_failures >= 3)

    def fail(self, error, *, invalidate=False):
        self.error = error
        self.invalid = self.invalid or invalidate
        if invalidate:
            self.raw_received = None


def validate_device(data, *, previous=None, legacy=False):
    def minimum_for(kind, value, previous_value):
        if kind not in DEFAULT_INTERVALS:
            raise InvalidValue("invalid_interval")
        unchanged = previous is not None and previous_value == value
        return MIN_INTERVALS[kind] if legacy or unchanged else CONFIGURABLE_MIN_INTERVALS[kind]

    model = data["model"]
    valid = {key for key, _, _ in channels(model)}
    if type(data["unit_id"]) is not int or not 1 <= data["unit_id"] <= 247:
        raise InvalidValue("invalid_unit")
    for kind, interval in data.get("intervals", {}).items():
        old = (
            previous.get("intervals", {}).get(kind, DEFAULT_INTERVALS.get(kind))
            if previous is not None
            else None
        )
        if not minimum_for(kind, interval, old) <= finite(interval) <= 3600:
            raise InvalidValue("invalid_interval")
    for key, options in data.get("channels", {}).items():
        if key not in valid:
            raise InvalidValue("invalid_channel")
        override = options.get("poll_interval")
        kind = key.rsplit("_", 1)[0]
        old = (
            previous.get("channels", {}).get(key, {}).get("poll_interval")
            if previous is not None
            else None
        )
        if override is not None and (
            type(override) is not int or not minimum_for(kind, override, old) <= override <= 3600
        ):
            raise InvalidValue("invalid_interval")
        if (
            key.startswith("temperature_")
            and type(options.get("allow_negative", False)) is not bool
        ):
            raise InvalidValue("invalid_temperature_option")
        # Persist permissions only for hardware-tested MB307D DO channels.
        if "write_enabled" in options:
            if type(options["write_enabled"]) is not bool:
                raise InvalidValue("invalid_write_permission")
            # Legacy MB308N AO/DO permissions remain stored for stable
            # config migration, but neither profile can transmit in b26.
            if options["write_enabled"] and not (
                key.startswith(("do_", "ao_"))
                and model in ("mb_307d_ii_s", "mb_308n")
            ):
                raise InvalidValue("unsupported_write_permission")
        if options.get("mode") not in (None, *MODES):
            raise InvalidValue("invalid_mode")
        if options.get("display", "physical") not in ("physical", "percent", "scaled"):
            raise InvalidValue("invalid_display")
        if key.startswith("ao_") and options.get("display") == "scaled":
            raise InvalidValue("invalid_display")
        if options.get("display") == "scaled":
            if finite(options["scale_min"]) == finite(options["scale_max"]):
                raise InvalidValue("invalid_scale")


def set_temperature_range_enabled(old, first: int, last: int, enabled: bool):
    """Set an inclusive TM-32DS temperature-channel range, retaining metadata."""
    if old.get("model") != "tm_32ds":
        raise InvalidValue("bulk_change_not_supported")
    if type(first) is not int or type(last) is not int or not 1 <= first <= last <= 32:
        raise InvalidValue("invalid_channel_range")
    if type(enabled) is not bool:
        raise InvalidValue("invalid_channel_state")
    updated = deepcopy(old)
    settings = updated.setdefault("channels", {})
    for index in range(first, last + 1):
        key = f"temperature_{index}"
        settings[key] = dict(settings.get(key, {})) | {"enabled": enabled}
    return revise_device(old, updated)


def disable_temperature_range(old, first: int, last: int):
    """Disable an explicitly chosen range; never infer wiring from unavailable values.

    This only affects TM-32DS polling and entity availability, not hardware I/O.
    Previously stored channel names and individual intervals are retained.
    """
    return set_temperature_range_enabled(old, first, last, False)


def revise_device(old, updated):
    """Preserve stable identity. Explicitly revoke on consequential changes."""
    new = deepcopy(updated)
    new["device_uid"] = old["device_uid"]
    moved = old["unit_id"] != new["unit_id"] or old.get("connection_uid") != new.get(
        "connection_uid"
    )
    for key, options in new.get("channels", {}).items():
        before = old.get("channels", {}).get(key, {})
        changed_output = key.startswith(("do_", "ao_")) and any(
            before.get(field) != options.get(field)
            for field in ("mode", "display", "scale_min", "scale_max")
        )
        if moved or changed_output or not options.get("enabled", True):
            options["write_enabled"] = False
    validate_device(new, previous=old)
    return new
