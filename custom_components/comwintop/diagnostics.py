"""No hostnames, paths, user names, values or private payloads in exports."""

import time

from .const import VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    guard = getattr(entry.runtime_data, "rtu_guard", None)
    return {
        "integration_version": VERSION,
        "transport": entry.data["transport"],
        "hardware_validated": False,
        "writes": "locked",
        "rtu_guard_enabled": guard.enabled if guard is not None else False,
        "shared_minimum_read_rate_hz": round(
            sum(u.minimum_read_rate_hz for u in entry.runtime_data.units.values()), 3
        ),
        "rtu_bus_unsafe": guard.unsafe if guard is not None else False,
        "rtu_bus_unsafe_reason": guard.reason if guard is not None else None,
        "rtu_transient_timeouts": guard.transient_timeouts if guard is not None else 0,
        "rtu_recovered_timeouts": guard.recovered_timeouts if guard is not None else 0,
        "rtu_timeout_unverified": (guard.unverified_after_timeout if guard is not None else False),
        "experimental_fc06_address_write": "disabled",
        "devices": [
            {
                "model": unit.model,
                "status": unit.status,
                "counters": dict(unit.counters),
                "timeout_history": unit.timeout_history,
                "bus_lock_wait_ms": unit.bus_lock_wait_ms,
                "read_call_ms": unit.read_call_ms,
                "minimum_read_rate_hz": unit.minimum_read_rate_hz,
                "poll_task_running": unit.poll_running,
                "seconds_since_last_response": (
                    round(time.monotonic() - unit.last_response, 1)
                    if unit.last_response is not None
                    else None
                ),
                "intervals": unit.intervals,
                "channels": {
                    key: {
                        "enabled": unit.enabled(key),
                        "effective_interval": unit.interval(key),
                        "interval_source": (
                            "individual"
                            if unit.options(key).get("poll_interval") is not None
                            else "group"
                        ),
                        "successful_reads_since_reload": sample.successful_reads,
                        "consecutive_read_failures": sample.consecutive_read_failures,
                        "consecutive_invalid_values": sample.consecutive_invalid_values,
                        "consecutive_probe_fault_values": sample.consecutive_probe_fault_values,
                        "seconds_between_successful_reads": (
                            sample.last_successful_read_delta_seconds
                        ),
                        "available": unit.available(key),
                        "error": sample.error,
                        "detection_state": unit.options(key).get("detection_state"),
                        "age_seconds": round(time.monotonic() - sample.received, 1)
                        if sample.received is not None
                        else None,
                    }
                    for key, sample in unit.samples.items()
                },
            }
            for unit in entry.runtime_data.units.values()
        ],
    }
