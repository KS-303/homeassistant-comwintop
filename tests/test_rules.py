import math
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.comwintop.model import Sample, revise_device, validate_device
from custom_components.comwintop.profiles import (
    MODES,
    PROFILES,
    InvalidValue,
    analog_display,
    analog_physical,
    decode_channel,
    decode_temperature,
    encode_output,
)
from custom_components.comwintop.transport import endpoint_key, params_from


@pytest.mark.parametrize("raw,expected", [(0, 0), (1, 0.1), (250, 25), (1250, 125)])
def test_temperature(raw, expected):
    assert decode_temperature(raw) == expected


@pytest.mark.parametrize("raw", [-1, 850, 1251, 32768, 65535, True, float("nan")])
def test_unknown_temperature_is_not_invented(raw):
    with pytest.raises(InvalidValue):
        decode_temperature(raw)


def test_channel32_address():
    g = PROFILES["tm_32ds"][0]
    assert g.start + g.count - 1 == 63


@pytest.mark.parametrize(
    "raw,nc,result",
    [(True, False, True), (True, True, False), (False, True, True), (False, False, False)],
)
def test_di_no_nc(raw, nc, result):
    assert decode_channel("di", raw, {"nc": nc}) is result


def test_di_unknown_never_healthy():
    with pytest.raises(InvalidValue):
        decode_channel("di", None, {"nc": True})


@pytest.mark.parametrize(
    "mode,value,raw",
    [("4_20ma", 4, 10000), ("4_20ma", 12, 30000), ("0_10v", 5, 25000), ("0_5v", 5, 25000)],
)
def test_output_formula(mode, value, raw):
    assert encode_output(value, mode) == raw
    assert analog_physical(raw, mode, True) == value


@pytest.mark.parametrize("value", [-0.1, 100.1, 120, math.nan, math.inf, -math.inf, True, None])
def test_bad_output_is_rejected_not_clamped(value):
    with pytest.raises(InvalidValue):
        encode_output(value, "0_10v", "percent")


@given(st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False))
def test_percent_roundtrip(value):
    for mode in MODES:
        raw = encode_output(value, mode, "percent")
        physical = analog_physical(raw, mode, True)
        assert abs(analog_display(physical, mode, {"display": "percent"}) - value) <= 0.0041


def test_input_output_5v_scaling_distinction():
    assert analog_physical(25000, "0_5v", False) == 2.5
    assert analog_physical(25000, "0_5v", True) == 5


def test_stale_deadline_not_extended_by_error():
    s = Sample()
    s.accept(20, 200, 100)
    s.fail("timeout")
    assert s.available(144.999, 15)
    assert not s.available(145, 15)
    assert s.received == 100
    s.fail("transport_lost", invalidate=True)
    assert not s.available(101, 15)
    s.accept(21, 210, 200)
    assert s.available(200, 15)


def device():
    return {
        "model": "mb_308n",
        "unit_id": 1,
        "device_uid": "stable",
        "connection_uid": "bus1",
        "channels": {
            "ao_1": {"enabled": True, "write_enabled": True, "mode": "0_10v"},
            "do_1": {"enabled": True, "write_enabled": True},
        },
    }


@pytest.mark.parametrize("change", ["unit", "bus", "disable", "scale"])
def test_permissions_revoked_only_when_required(change):
    old = device()
    new = deepcopy(old)
    if change == "unit":
        new["unit_id"] = 2
    if change == "bus":
        new["connection_uid"] = "bus2"
    if change == "disable":
        new["channels"]["ao_1"]["enabled"] = False
    if change == "scale":
        new["channels"]["ao_1"]["display"] = "percent"
    out = revise_device(old, new)
    assert out["device_uid"] == "stable"
    assert out["channels"]["ao_1"]["write_enabled"] is False
    assert out["channels"]["do_1"]["write_enabled"] is (change not in ("unit", "bus"))
    assert old["channels"]["ao_1"]["write_enabled"] is True


def test_restart_keeps_permissions_not_commands():
    old = device()
    out = revise_device(old, old)
    assert out["channels"]["ao_1"]["write_enabled"] is True
    assert "queue" not in out


@pytest.mark.parametrize("unit", [0, 248, -1, True, 1.5])
def test_no_broadcast_or_invalid_unit(unit):
    d = device()
    d["unit_id"] = unit
    with pytest.raises(InvalidValue):
        validate_device(d)


@pytest.mark.parametrize("interval", [0, 0.1, math.inf, math.nan, 3601])
def test_poll_load_limits(interval):
    d = device()
    d["intervals"] = {"di": interval}
    with pytest.raises(InvalidValue):
        validate_device(d)


def test_transports_do_not_guess_ports_or_framing():
    assert params_from({"transport": "tcp", "host": "EXAMPLE.local", "port": 1502}).port == 1502
    assert endpoint_key(
        {"transport": "tcp_gateway", "host": "EXAMPLE.local", "port": 1502}
    ) == endpoint_key({"transport": "tcp", "host": "example.local", "port": 1502})
    p = params_from({"transport": "rtu_tcp", "host": "127.0.0.1", "port": 8899, "baudrate": 9600})
    assert p.device == "socket://127.0.0.1:8899" and p.baudrate == 9600
    with pytest.raises(ValueError):
        params_from({"transport": "serial", "device": "/tmp/foo"})
