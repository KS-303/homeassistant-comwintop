"""Public-beta diagnostics must not expose connection details or channel readings."""

import json
import time
from collections import Counter
from types import SimpleNamespace

from custom_components.comwintop.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redact_connection_identity_and_measurements():
    """Export health counters and effective intervals, not private config or values."""
    secret_host = "private-gateway.example.invalid"
    secret_name = "PRIVATE_DEVICE_LABEL"
    secret_user = "PRIVATE_TEST_USERNAME"
    secret_password = "PRIVATE_TEST_CREDENTIAL"
    secret_device_id = "PRIVATE_TEST_UNIT_UUID"
    secret_raw = 424242
    secret_value = 909090

    good_sample = SimpleNamespace(
        received=time.monotonic() - 2,
        raw=secret_raw,
        value=secret_value,
        error=None,
        successful_reads=3,
        consecutive_read_failures=0,
        consecutive_invalid_values=0,
        consecutive_probe_fault_values=0,
        last_successful_read_delta_seconds=5.2,
    )
    bad_sample = SimpleNamespace(
        received=None,
        raw=secret_raw,
        value=None,
        error="timeout",
        successful_reads=0,
        consecutive_read_failures=2,
        consecutive_invalid_values=0,
        consecutive_probe_fault_values=0,
        last_successful_read_delta_seconds=None,
    )
    unit = SimpleNamespace(
        model="tm_32ds",
        status="SUSPECT",
        counters=Counter({"responses": 3, "timeout": 1}),
        latency_ms=37.1,
        _poll_task=None,
        last_response=time.monotonic() - 2,
        intervals={"temperature": 15},
        samples={"temperature_1": good_sample, "temperature_2": bad_sample},
        options=lambda key: {"poll_interval": 5} if key == "temperature_1" else {},
        enabled=lambda key: key == "temperature_1",
        interval=lambda key: 5 if key == "temperature_1" else 30,
        available=lambda key: key == "temperature_1",
    )
    entry = SimpleNamespace(
        data={
            "transport": "rtu_tcp",
            "host": secret_host,
            "port": 8234,
            "name": secret_name,
            "username": secret_user,
            "password": secret_password,
        },
        runtime_data=SimpleNamespace(units={secret_device_id: unit}),
    )

    exported = await async_get_config_entry_diagnostics(None, entry)

    assert exported["transport"] == "rtu_tcp"
    assert exported["writes"] == "locked"
    assert exported["hardware_validated"] is False
    assert len(exported["devices"]) == 1
    device = exported["devices"][0]
    assert device["counters"] == {"responses": 3, "timeout": 1}
    assert device["poll_task_running"] is False
    assert device["seconds_since_last_response"] >= 0
    assert device["channels"]["temperature_1"]["effective_interval"] == 5
    assert device["channels"]["temperature_1"]["interval_source"] == "individual"
    assert device["channels"]["temperature_1"]["successful_reads_since_reload"] == 3
    assert device["channels"]["temperature_1"]["seconds_between_successful_reads"] == 5.2
    assert device["channels"]["temperature_2"]["interval_source"] == "group"
    assert device["channels"]["temperature_1"]["age_seconds"] >= 0
    assert device["channels"]["temperature_2"]["age_seconds"] is None
    assert device["channels"]["temperature_2"]["error"] == "timeout"

    serialized = json.dumps(exported, ensure_ascii=False)
    for forbidden in (
        secret_host,
        secret_name,
        secret_user,
        secret_password,
        secret_device_id,
        str(secret_raw),
        str(secret_value),
        '"port"',
        '"username"',
        '"password"',
    ):
        assert forbidden not in serialized
