"""Stable names and beta limits; no hardware validation is implied."""

DOMAIN = "comwintop"
VERSION = "0.1.0b15"
PLATFORMS = ["sensor", "binary_sensor", "switch", "number"]
DEFAULT_INTERVALS = {"temperature": 15, "di": 2, "do": 2, "ai": 10, "ao": 10}
MIN_INTERVALS = {"temperature": 5, "di": 1, "do": 1, "ai": 2, "ao": 2}
STALE_FACTOR = 3
WRITE_TTL = 2.0
READBACK_ATTEMPTS = 3
READBACK_DELAY = 0.2
# No user option can bypass the hardware release gate.
HARDWARE_VALIDATED_WRITES: frozenset[tuple[str, str, str]] = frozenset()
