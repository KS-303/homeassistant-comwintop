"""Single-shot FC05 on the *existing* Home Assistant tmodbus RTU/TCP link.

LAB ONLY: pinned to the exact backend implementations audited here.
No second socket or Modbus master.  There is deliberately no retry path.
All private backend accesses fail closed on an unexpected implementation.
"""

import asyncio
import time
from importlib.metadata import PackageNotFoundError, version

from modbus_connection.tmodbus import TmodbusUnit
from tmodbus.pdu import WriteSingleCoilPDU
from tmodbus.transport.async_rtu import AsyncRtuTransport
from tmodbus.transport.async_smart import AsyncSmartTransport

SUPPORTED = {"modbus-connection": "4.12.7", "tmodbus": "1.1.0"}


class SingleAttemptUnavailable(RuntimeError):
    """The backend cannot prove one transport attempt before sending."""


def _require_backend_versions():
    for package, expected in SUPPORTED.items():
        try:
            actual = version(package)
        except PackageNotFoundError as err:
            raise SingleAttemptUnavailable(f"{package}_not_installed") from err
        if actual != expected:
            raise SingleAttemptUnavailable(f"{package}_version_{actual}_unsupported")


def _existing_connection(unit):
    _require_backend_versions()
    if not isinstance(unit, TmodbusUnit):
        raise SingleAttemptUnavailable("not_tmodbus_unit")
    conn = unit._conn
    if not conn.connected:
        raise SingleAttemptUnavailable("shared_connection_not_open")
    client = unit._client
    transport = client.transport
    if not isinstance(transport, AsyncSmartTransport):
        raise SingleAttemptUnavailable("not_smart_transport")
    base = transport.base_transport
    if not isinstance(base, AsyncRtuTransport):
        raise SingleAttemptUnavailable("not_rtu_transport")
    if not base.port.startswith("socket://"):
        raise SingleAttemptUnavailable("not_rtu_tcp_socket")
    if not base.is_open() or transport._must_reconnect:
        raise SingleAttemptUnavailable("shared_rtu_link_requires_recovery")
    return conn, client, transport, base


async def fc05_once(unit, address: int, value: bool, guard, *, timeout: float = 4.0):
    """Send FC05 once through the shared backend's *base* RTU transport.

    Called with the ComWinTop hub lock already held. The backend's pacer and
    communication lock also protect other users of this same HA connection.
    No connect or reconnect is performed by this call. The guard is executed
    after both locks, before the single underlying transport call.
    """
    if type(address) is not int or not 0 <= address <= 7 or type(value) is not bool:
        raise ValueError("unsupported_fc05_address_or_value")
    conn, client, transport, base = _existing_connection(unit)
    async with conn._pacer.paced(unit._unit_id):
        async with transport._communication_lock:
            # The shared backend may have reconnected while waiting for a lock.
            current_conn, current_client, current_transport, current_base = (
                _existing_connection(unit)
            )
            if (
                current_conn is not conn
                or current_client is not client
                or current_transport is not transport
                or current_base is not base
            ):
                raise SingleAttemptUnavailable("shared_connection_changed")
            guard()
            try:
                # Unlike AsyncSmartTransport.send_and_receive, this invokes
                # exactly ONE base RTU request: no Busy/timeout/reconnect retry.
                async with asyncio.timeout(timeout):
                    result = await base.send_and_receive(
                        unit._unit_id, WriteSingleCoilPDU(address, value)
                    )
            finally:
                # Preserve the tmodbus pacer's timing for subsequent HA calls.
                transport._last_request_finished_at = time.monotonic()
    if type(result) is not bool:
        raise ValueError("unexpected_fc05_ack_type")
    if result != value:
        raise ValueError("fc05_ack_mismatch")
    return result
