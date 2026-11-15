"""No hostnames, paths, user names, values or private payloads in exports."""

import time

from .const import VERSION


async def async_get_config_entry_diagnostics(hass, entry):
    return {
        "integration_version": VERSION,
        "transport": entry.data["transport"],
        "hardware_validated": False,
        "writes": "locked",
        "devices": [
            {
                "model": unit.model,
                "status": unit.status,
                "counters": dict(unit.counters),
                "latency_ms": unit.latency_ms,
                "intervals": unit.intervals,
                "channels": {
                    key: {
                        "enabled": unit.enabled(key),
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
