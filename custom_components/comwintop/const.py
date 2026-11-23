"""Stable names and beta limits; no hardware validation is implied."""

DOMAIN = "comwintop"
VERSION = "0.1.0b25"
PLATFORMS = ["sensor", "binary_sensor", "switch", "number"]
DEFAULT_INTERVALS = {"temperature": 15, "di": 2, "do": 2, "ai": 10, "ao": 10}
MIN_INTERVALS = {"temperature": 5, "di": 1, "do": 1, "ai": 2, "ao": 2}
# Existing short intervals remain loadable; new MB settings must leave room
# for its four separate function-code blocks on a one-second-paced bus.
CONFIGURABLE_MIN_INTERVALS = {"temperature": 5, "di": 5, "do": 5, "ai": 5, "ao": 5}
NEW_DEVICE_INTERVALS = DEFAULT_INTERVALS | {"di": 8, "do": 8, "ai": 20, "ao": 20}
STALE_FACTOR = 3
BUS_MESSAGE_SPACING = 1.0  # End of previous exchange to start of next, on shared HA link.
READ_DEADLINE = 4.0  # Original 3 s request budget plus one pacing slot.
WRITE_TTL = 2.0
READBACK_ATTEMPTS = 3
READBACK_DELAY = 0.2
# No user option can bypass the hardware release gate.
HARDWARE_VALIDATED_WRITES: frozenset[tuple[str, str, str]] = frozenset()
