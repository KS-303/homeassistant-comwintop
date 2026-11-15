"""Documented profiles. Unknown temperature encodings fail closed."""

import math
from dataclasses import dataclass


class InvalidValue(ValueError):
    """A value cannot be represented or safely interpreted."""


@dataclass(frozen=True)
class Group:
    kind: str
    method: str
    start: int
    count: int


PROFILES = {
    "tm_32ds": (Group("temperature", "read_holding_registers", 32, 32),),
    "mb_308n": (
        Group("di", "read_discrete_inputs", 0, 8),
        Group("do", "read_coils", 0, 8),
        Group("ai", "read_input_registers", 0, 8),
        Group("ao", "read_holding_registers", 0, 4),
    ),
}
MODEL_NAMES = {"tm_32ds": "CWT-TM-32DS", "mb_308n": "CWT-MB308N"}
# (physical minimum, maximum, raw units per physical unit for input/output)
MODES = {
    "0_10v": (0.0, 10.0, 5000.0, 5000.0, "V"),
    "0_5v": (0.0, 5.0, 10000.0, 5000.0, "V"),
    "0_20ma": (0.0, 20.0, 2500.0, 2500.0, "mA"),
    "4_20ma": (4.0, 20.0, 2500.0, 2500.0, "mA"),
}


def finite(value):
    if isinstance(value, bool):
        raise InvalidValue("boolean_is_not_a_number")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise InvalidValue("invalid_number") from err
    if not math.isfinite(number):
        raise InvalidValue("non_finite")
    return number


def decode_temperature(raw):
    if type(raw) is not int or not 0 <= raw <= 1250:
        raise InvalidValue("temperature_encoding_unverified")
    if raw == 850:
        # A real 85 C measurement is indistinguishable from a power-up value
        # until the device's status/sentinel behavior has been measured.
        raise InvalidValue("temperature_85_ambiguous")
    return raw / 10


def analog_physical(raw, mode, output=False):
    if type(raw) is not int or not 0 <= raw <= 65535 or mode not in MODES:
        raise InvalidValue("invalid_analog_raw_or_mode")
    low, high, ai_divisor, ao_divisor, _ = MODES[mode]
    value = raw / (ao_divisor if output else ai_divisor)
    if not low <= value <= high:
        raise InvalidValue("analog_out_of_range")
    return value


def analog_display(physical, mode, options):
    low, high, *_ = MODES[mode]
    if options.get("display") == "percent":
        return (physical - low) * 100 / (high - low)
    if options.get("display") == "scaled":
        start, end = finite(options["scale_min"]), finite(options["scale_max"])
        if start == end:
            raise InvalidValue("invalid_scale")
        return start + (physical - low) * (end - start) / (high - low)
    return physical


def encode_output(value, mode, display="physical"):
    value = finite(value)
    if mode not in MODES:
        raise InvalidValue("invalid_mode")
    low, high, _, divisor, _ = MODES[mode]
    if display == "percent":
        if not 0 <= value <= 100:
            raise InvalidValue("out_of_range")
        value = low + value * (high - low) / 100
    elif display != "physical":
        raise InvalidValue("invalid_display")
    if not low <= value <= high:
        raise InvalidValue("out_of_range")
    return round(value * divisor)


def channel_key(kind, index):
    return f"{kind}_{index + 1}"


def channels(model):
    for group in PROFILES[model]:
        for index in range(group.count):
            yield channel_key(group.kind, index), group, index


def decode_channel(kind, raw, options):
    if kind == "temperature":
        return decode_temperature(raw)
    if kind in ("di", "do"):
        if type(raw) is not bool:
            raise InvalidValue("invalid_bit")
        return not raw if kind == "di" and options.get("nc", False) else raw
    # Analog channels require an explicit physical-mode selection first.
    mode = options.get("mode")
    physical = analog_physical(raw, mode, output=kind == "ao")
    return analog_display(physical, mode, options) if kind == "ai" else physical
