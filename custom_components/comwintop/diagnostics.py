"""No hostnames, paths, user names, values or private payloads in exports."""

import time

from .const import VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    return {
        "integration_version": VERSION,
        "transport": entry.data["transport"],
        "hardware_validated": False,
        "writes": "locked",
        "experimental_fc06_address_write": "disabled",
        "devices": [
            {
                "model": unit.model,
                "status": unit.status,
                "counters": dict(unit.counters),
                "latency_ms": unit.latency_ms,
                "poll_task_running": bool(unit._poll_task and not unit._poll_task.done()),
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
                        "seconds_between_successful_reads": (
                            sample.last_successful_read_delta_seconds
                        ),
                        "available": unit.available(key),
                        "error": sample.error,
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
