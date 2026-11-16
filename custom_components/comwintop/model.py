"""Pure, deterministic quality and configuration rules."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone

from .const import DEFAULT_INTERVALS, MIN_INTERVALS, STALE_FACTOR
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
        self.last_successful_read_utc = datetime.now(timezone.utc).isoformat()
        self.raw_received = now
        self.error, self.invalid = None, False

    def fail(self, error, *, invalidate=False):
        self.error = error
        self.invalid = self.invalid or invalidate
        if invalidate:
            self.raw_received = None


def validate_device(data):
    model = data["model"]
    valid = {key for key, _, _ in channels(model)}
    if type(data["unit_id"]) is not int or not 1 <= data["unit_id"] <= 247:
        raise InvalidValue("invalid_unit")
    for kind, interval in data.get("intervals", {}).items():
        if kind not in DEFAULT_INTERVALS or not MIN_INTERVALS[kind] <= finite(interval) <= 3600:
            raise InvalidValue("invalid_interval")
    for key, options in data.get("channels", {}).items():
        if key not in valid:
            raise InvalidValue("invalid_channel")
        override = options.get("poll_interval")
        if override is not None and (
            type(override) is not int
            or not MIN_INTERVALS[key.rsplit("_", 1)[0]] <= override <= 3600
        ):
            raise InvalidValue("invalid_interval")
        if options.get("mode") not in (None, *MODES):
            raise InvalidValue("invalid_mode")
        if options.get("display", "physical") not in ("physical", "percent", "scaled"):
            raise InvalidValue("invalid_display")
        if key.startswith("ao_") and options.get("display") == "scaled":
            raise InvalidValue("invalid_display")
        if options.get("display") == "scaled":
            if finite(options["scale_min"]) == finite(options["scale_max"]):
                raise InvalidValue("invalid_scale")


def revise_device(old, updated):
    """Preserve stable identity. Explicitly revoke on consequential changes."""
    new = deepcopy(updated)
    new["device_uid"] = old["device_uid"]
    moved = old["unit_id"] != new["unit_id"] or old.get("connection_uid") != new.get(
        "connection_uid"
    )
    for key, options in new.get("channels", {}).items():
        before = old.get("channels", {}).get(key, {})
        changed_output = key.startswith("ao_") and any(
            before.get(field) != options.get(field)
            for field in ("mode", "display", "scale_min", "scale_max")
        )
        if moved or changed_output or not options.get("enabled", True):
            options["write_enabled"] = False
    validate_device(new)
    return new
