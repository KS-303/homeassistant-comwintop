"""Documented profiles. Unknown temperature encodings fail closed."""

import math
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


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
    "mb_307d_ii_s": (
        Group("di", "read_discrete_inputs", 0, 8),
        Group("do", "read_coils", 0, 8),
        # AI register access confirmed; physical scaling remains unverified.
        Group("ai", "read_holding_registers", 50, 8),
    ),
    "mb_308n": (
        Group("di", "read_discrete_inputs", 0, 8),
        Group("do", "read_coils", 0, 8),
        Group("ai", "read_input_registers", 0, 8),
        Group("ao", "read_holding_registers", 0, 4),
    ),
}
MODEL_NAMES = {
    "tm_32ds": "CWT-TM-32DS",
    "mb_308n": "CWT-MB308N",
    "mb_307d_ii_s": "CWT-MB307D(II)-S",
}
BUILTIN_PROFILES = dict(PROFILES)
BUILTIN_NAMES = dict(MODEL_NAMES)
READ_METHODS = {
    "temperature": "read_holding_registers",
    "di": "read_discrete_inputs",
    "do": "read_coils",
    "ai": "read_input_registers",
    "ao": "read_holding_registers",
}
DECODERS = {
    "temperature": "tm_32ds_temperature",
    "di": "digital_input",
    "do": "digital_output_readback",
    "ai": "mb_308n_analog_input",
    "ao": "mb_308n_analog_output_readback",
}


class UniqueKeyLoader(yaml.SafeLoader):
    """Refuse ambiguous YAML mappings instead of silently taking the last key."""


def _unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if not isinstance(key, str) or key in result:
            raise InvalidValue("duplicate_or_non_string_yaml_key")
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def parse_profile(source, *, filename=None):
    """Compile a declarative, read-only device profile; never execute file content."""
    try:
        data = yaml.load(source, Loader=UniqueKeyLoader)
    except yaml.YAMLError as err:
        raise InvalidValue("invalid_profile_yaml") from err
    if not isinstance(data, dict) or set(data) != {"version", "model", "name", "groups"}:
        raise InvalidValue("invalid_profile_fields")
    model, name, groups = data["model"], data["name"], data["groups"]
    if type(data["version"]) is not int or data["version"] != 1:
        raise InvalidValue("unsupported_profile_version")
    if not isinstance(model, str) or not re.fullmatch(r"[a-z][a-z0-9_]{2,39}", model):
        raise InvalidValue("invalid_model_id")
    if filename is not None and filename != f"{model}.yaml":
        raise InvalidValue("profile_filename_mismatch")
    if model in BUILTIN_PROFILES:
        raise InvalidValue("builtin_profile_locked")
    if not isinstance(name, str) or not 3 <= len(name.strip()) <= 80 or name != name.strip():
        raise InvalidValue("invalid_model_name")
    if not isinstance(groups, list) or not 1 <= len(groups) <= len(READ_METHODS):
        raise InvalidValue("invalid_groups")
    compiled = []
    seen = set()
    for item in groups:
        if not isinstance(item, dict) or set(item) != {
            "kind",
            "method",
            "decoder",
            "start",
            "count",
        }:
            raise InvalidValue("invalid_group_fields")
        kind, method, start, count = (item[k] for k in ("kind", "method", "start", "count"))
        if (
            not isinstance(kind, str)
            or kind not in READ_METHODS
            or method != READ_METHODS[kind]
            or item["decoder"] != DECODERS[kind]
            or kind in seen
        ):
            raise InvalidValue("unverified_read_method_or_duplicate_group")
        if type(start) is not int or type(count) is not int:
            raise InvalidValue("invalid_register_range")
        # A single short request per group keeps polling bounded on serial buses.
        if not 0 <= start <= 65535 or not 1 <= count <= 64 or start + count > 65536:
            raise InvalidValue("invalid_register_range")
        seen.add(kind)
        compiled.append(Group(kind, method, start, count))
    return model, name, tuple(compiled)


def load_local_profiles(root: Path):
    """Load verified local profiles with a last-valid snapshot per model."""
    root = Path(root)
    active = root / "profiles"
    backup = root / "last_valid"
    result = {}
    failures = {}
    if not active.is_dir() and not backup.is_dir():
        return result, failures
    for path in sorted(active.glob("*.yaml")):
        try:
            if path.is_symlink() or path.stat().st_size > 16_384:
                raise InvalidValue("invalid_profile_file")
            source = path.read_text(encoding="utf-8")
            model, name, groups = parse_profile(source, filename=path.name)
            if model in result:
                raise InvalidValue("duplicate_profile")
            result[model] = name, groups
            backup.mkdir(parents=True, exist_ok=True)
            previous = backup / path.name
            if not previous.exists() or previous.read_text(encoding="utf-8") != source:
                # Keep a known valid previous revision for explicit rollback.
                if previous.is_file() and not previous.is_symlink():
                    old = previous.read_text(encoding="utf-8")
                    parse_profile(old, filename=path.name)
                    older = backup / f"{path.stem}.previous"
                    older_tmp = backup / f".{path.stem}.previous.new"
                    older_tmp.write_text(old, encoding="utf-8")
                    older_tmp.replace(older)
                temporary = backup / f".{path.stem}.new"
                temporary.write_text(source, encoding="utf-8")
                temporary.replace(previous)
        except (OSError, UnicodeError, InvalidValue) as err:
            failures[path.name] = str(err)
            previous = backup / path.name
            try:
                if previous.is_file() and not previous.is_symlink():
                    model, name, groups = parse_profile(
                        previous.read_text(encoding="utf-8"), filename=path.name
                    )
                    result[model] = name, groups
            except (OSError, UnicodeError, InvalidValue):
                pass
    if backup.is_dir():
        for path in sorted(backup.glob("*.yaml")):
            if path.name in {f"{model}.yaml" for model in result} or path.is_symlink():
                continue
            try:
                model, name, groups = parse_profile(
                    path.read_text(encoding="utf-8"), filename=path.name
                )
                result[model] = name, groups
                failures[path.name] = "active_profile_missing_using_last_valid"
            except (OSError, UnicodeError, InvalidValue):
                pass
    return result, failures


def publish_local_profiles(local):
    """Publish a complete validated snapshot on the HA event-loop thread.

    This function has no awaits; a concurrent coroutine never sees partially
    cleared profile mappings. Do not call it from an executor worker.
    """
    next_profiles = dict(BUILTIN_PROFILES)
    next_names = dict(BUILTIN_NAMES)
    for model, (name, groups) in local.items():
        next_profiles[model] = groups
        next_names[model] = name
    # Imported dict references remain stable. All changes run synchronously
    # on the same HA event loop, rather than from a background executor.
    PROFILES.clear()
    PROFILES.update(next_profiles)
    MODEL_NAMES.clear()
    MODEL_NAMES.update(next_names)


def install_local_profiles(root: Path):
    """Synchronous setup helper for tests/offline use, not executor threads."""
    local, failures = load_local_profiles(root)
    publish_local_profiles(local)
    return failures


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


def decode_temperature(raw, allow_negative=False):
    if type(raw) is not int or not 0 <= raw <= 65535:
        raise InvalidValue("temperature_encoding_unverified")
    if raw == 0xFC18:
        raise InvalidValue("probe_disconnected")
    signed = raw - 65536 if raw & 0x8000 else raw
    if signed < 0 and not allow_negative:
        raise InvalidValue("negative_temperature_unverified")
    if not -550 <= signed <= 1250:
        raise InvalidValue("temperature_encoding_unverified")
    if signed == 850:
        # A real 85 C measurement is indistinguishable from a power-up value
        # until the device's status/sentinel behavior has been measured.
        raise InvalidValue("temperature_85_ambiguous")
    return signed / 10


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


def decode_channel(kind, raw, options, *, model=None):
    if kind == "temperature":
        return decode_temperature(raw, options.get("allow_negative", False))
    if kind in ("di", "do"):
        if type(raw) is not bool:
            raise InvalidValue("invalid_bit")
        return not raw if kind == "di" and options.get("nc", False) else raw
    # MB307D AI0–AI7 read correctly on FC03/50–57, but signal range and
    # engineering units have not been hardware-validated. Keep values
    # unavailable while retaining the raw reply for diagnostics.
    if model == "mb_307d_ii_s" and kind == "ai":
        raise InvalidValue("mb307d_analog_scaling_unverified")
    # Analog channels require an explicit physical-mode selection first.
    mode = options.get("mode")
    physical = analog_physical(raw, mode, output=kind == "ao")
    return analog_display(physical, mode, options) if kind == "ai" else physical
