"""Read-only communication-register profiles; no configuration write path."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CommunicationProfile:
    model: str
    register: int | None
    read_method: str | None
    write_function: int | None
    register_read_validated: bool
    write_enabled: bool = False


PROFILES = {
    "tm_32ds": CommunicationProfile("tm_32ds", 16, "read_holding_registers", 6, True),
    "mb_308n": CommunicationProfile("mb_308n", None, None, None, False),
}


def plan_tm32ds_address(raw: int, current_id: int, target_id: int, configured_ids=()) -> int:
    """Pure preview: replace only the address byte; never perform a write."""
    if type(raw) is not int or not 0 <= raw <= 0xFFFF:
        raise ValueError("invalid_register")
    if type(target_id) is not int or not 1 <= target_id <= 247:
        raise ValueError("invalid_address")
    if raw >> 8 != current_id:
        raise ValueError("address_mismatch")
    if target_id in configured_ids and target_id != current_id:
        raise ValueError("configured_address_conflict")
    if target_id == current_id:
        raise ValueError("unchanged_address")
    return target_id << 8 | (raw & 0xFF)


def inspect_tm32ds(raw: int, configured_id: int) -> dict[str, str]:
    """Only the observed 0x04 low byte is decoded; other encodings are unknown."""
    if not 0 <= raw <= 0xFFFF:
        raise ValueError("invalid_register")
    address = raw >> 8
    low = raw & 0xFF
    known = low == 0x04
    return {
        "address": str(address),
        "configured_address": str(configured_id),
        "baudrate": "9600" if known else "?",
        "parity": "N" if known else "?",
        "databits": "8" if known else "?",
        "stopbits": "1" if known else "?",
        "raw": f"0x{raw:04X}",
        "status": "read_only",
    }
