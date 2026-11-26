"""Opt-in relay recovery intent; never persist old commands."""

import json
from hashlib import sha256
from pathlib import Path

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import HARDWARE_VALIDATED_WRITES
from .transport import endpoint_key


def recovery_targets(connection, settings):
    """Only explicitly permitted outputs on the released lab backend."""
    if (
        settings.get("model"),
        connection.get("transport"),
        "fc05",
    ) not in HARDWARE_VALIDATED_WRITES:
        return {}
    result = {}
    for index in range(1, 9):
        key = f"do_{index}"
        options = settings.get("channels", {}).get(key, {})
        state = options.get("recovery_state", "hold")
        if (
            options.get("enabled", True) is True
            and options.get("write_enabled", False) is True
            and state in ("off", "on")
        ):
            result[key] = state == "on"
    return result


class RecoveryStore:
    """Persist only a recovery marker, scoped to device and endpoint."""

    def __init__(self, hass, entry, subentry):
        self.hass = hass
        endpoint = endpoint_key(dict(entry.data))
        identity = (
            f"{entry.entry_id}:{subentry.data['device_uid']}:{subentry.data['unit_id']}:{endpoint}"
        )
        digest = sha256(identity.encode()).hexdigest()[:32]
        self.store = Store(hass, 1, f"comwintop.relay_recovery.{digest}")

    async def load(self):
        """Return None for absent marker; reject malformed existing markers."""

        def read():
            path = Path(self.store.path)
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                data = envelope["data"]
                if (
                    envelope["key"] == self.store.key
                    and set(data) == {"pending"}
                    and type(data["pending"]) is bool
                ):
                    return data["pending"]
            except FileNotFoundError:
                return None
            except (OSError, ValueError, KeyError, TypeError):
                pass
            raise HomeAssistantError("Invalid relay recovery marker; writes blocked")

        return await self.hass.async_add_executor_job(read)

    async def save(self, pending):
        await self.store.async_save({"pending": pending})
        if await self.load() is not pending:
            raise HomeAssistantError("Relay recovery marker could not be verified")
