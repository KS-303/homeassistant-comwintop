"""MB307D(II)-S hardware results and guarded write-release regression checks."""

import pytest

from custom_components.comwintop.const import HARDWARE_VALIDATED_WRITES
from custom_components.comwintop.model import revise_device, validate_device
from custom_components.comwintop.profiles import (
    PROFILES,
    InvalidValue,
    channels,
    decode_channel,
)


def device(*, unit_id=1, channels_config=None):
    return {
        "model": "mb_307d_ii_s",
        "unit_id": unit_id,
        "device_uid": "mb307d-lab",
        "channels": channels_config or {},
    }


def test_hardware_verified_read_register_layout():
    groups = PROFILES["mb_307d_ii_s"]
    assert [(g.kind, g.method, g.start, g.count) for g in groups] == [
        ("di", "read_discrete_inputs", 0, 8),
        ("do", "read_coils", 0, 8),
        ("ai", "read_holding_registers", 50, 8),
    ]
    assert len(list(channels("mb_307d_ii_s"))) == 24


def test_discrete_registers_decode_but_analog_scale_is_not_invented():
    assert decode_channel("di", True, {}, model="mb_307d_ii_s") is True
    assert decode_channel("di", True, {"nc": True}, model="mb_307d_ii_s") is False
    assert decode_channel("do", False, {}, model="mb_307d_ii_s") is False
    with pytest.raises(InvalidValue, match="mb307d_analog_scaling_unverified"):
        decode_channel("ai", 0, {"mode": "0_10v"}, model="mb_307d_ii_s")


def test_write_permission_only_valid_for_mb307d_digital_outputs():
    validate_device(device(channels_config={"do_1": {"write_enabled": True}}))
    with pytest.raises(InvalidValue, match="unsupported_write_permission"):
        validate_device(device(channels_config={"di_1": {"write_enabled": True}}))
    with pytest.raises(InvalidValue, match="invalid_write_permission"):
        validate_device(device(channels_config={"do_1": {"write_enabled": 1}}))
    with pytest.raises(InvalidValue, match="unsupported_write_permission"):
        validate_device(
            {
                "model": "mb_308n",
                "unit_id": 1,
                "device_uid": "mb308n-lab",
                "channels": {"do_1": {"write_enabled": True}},
            }
        )


def test_move_or_disabling_output_revokes_permission():
    old = device(channels_config={"do_1": {"write_enabled": True}})
    new = revise_device(old, device(unit_id=3, channels_config={"do_1": {"write_enabled": True}}))
    assert new["channels"]["do_1"]["write_enabled"] is False
    assert new["device_uid"] == old["device_uid"]

    disabled = revise_device(
        old,
        device(channels_config={"do_1": {"write_enabled": True, "enabled": False}}),
    )
    assert disabled["channels"]["do_1"]["write_enabled"] is False


def test_write_release_gate_stays_locked_until_transport_certified():
    assert ("mb_307d_ii_s", "rtu_tcp", "fc05") not in HARDWARE_VALIDATED_WRITES
    assert not HARDWARE_VALIDATED_WRITES
