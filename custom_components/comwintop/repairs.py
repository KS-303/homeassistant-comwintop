"""User-confirmed recovery for a latched, read-only RTU bus.

Only the repair flow can clear the persisted bus marker. This operation does
not claim to prove that a power cycle drained every possible gateway buffer.
"""

import json
from pathlib import Path

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .recovery import RecoveryStore, recovery_targets
from .rtu_safety import RtuSessionGuard


class RtuRecoveryFlow(RepairsFlow):
    """Require three independent physical-safety confirmations."""

    async def async_step_init(self, user_input=None):
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        fields = {
            vol.Required("bus_power_cycled"): bool,
            vol.Required("sole_master_confirmed"): bool,
            vol.Required("gateway_queues_cleared"): bool,
        }
        if user_input is None:
            return self.async_show_form(step_id="confirm", data_schema=vol.Schema(fields))
        try:
            vol.Schema(fields)(user_input)
            if not all(
                user_input.get(field) is True
                for field in (
                    "bus_power_cycled",
                    "sole_master_confirmed",
                    "gateway_queues_cleared",
                )
            ):
                raise vol.Invalid("incomplete")
        except vol.Invalid:
            return self.async_show_form(
                step_id="confirm", data_schema=vol.Schema(fields), errors={"base": "incomplete"}
            )
        marker_key = (self.data or {}).get("marker_key")
        if not isinstance(marker_key, str) or not marker_key.startswith("comwintop.rtu_session."):
            raise HomeAssistantError("Missing RTU recovery marker")
        expected_issue = f"rtu_{marker_key.rsplit('.', 1)[-1]}"
        if self.issue_id != expected_issue:
            raise HomeAssistantError("Recovery marker does not match issue")
        # Never reset while this physical endpoint is still being polled.
        matching = []
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            gate = getattr(getattr(entry, "runtime_data", None), "rtu_guard", None)
            if gate is not None and gate.marker_key == marker_key:
                matching.append((entry, gate))
        if any(gate.inflight or not gate.unsafe for _, gate in matching):
            raise HomeAssistantError("RTU bus is not safely stopped")
        store = Store(self.hass, 1, marker_key)
        saved = await store.async_load()
        if not isinstance(saved, dict) or saved.get("active") is not True:
            raise HomeAssistantError("RTU marker not in expected active state")
        # Record explicit targets before allowing the physical bus to reopen.
        # Include entries that lost their runtime during a Home Assistant restart.
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("transport") != "rtu_tcp":
                continue
            gate = RtuSessionGuard(self.hass, entry)
            if marker_key != gate.marker_key and (
                gate._legacy_store is None or marker_key != gate._legacy_store.key
            ):
                continue
            for sub in entry.subentries.values():
                if recovery_targets(entry.data, sub.data):
                    await RecoveryStore(self.hass, entry, sub).save(True)
        await store.async_save({"active": False})

        def persisted():
            try:
                payload = json.loads(Path(store.path).read_text(encoding="utf-8"))
                return payload.get("key") == marker_key and payload.get("data") == {"active": False}
            except (OSError, ValueError, AttributeError):
                return False

        if not await self.hass.async_add_executor_job(persisted):
            raise HomeAssistantError("RTU marker reset could not be verified")
        # No auto-restart or stale queued writes; operator uses reload after
        # the Repairs flow has completed.
        for entry, _ in matching:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data={})


async def async_create_fix_flow(hass, issue_id, data):
    """HA Repairs platform entry point."""
    return RtuRecoveryFlow()
