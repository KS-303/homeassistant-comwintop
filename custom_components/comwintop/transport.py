"""Only the HA shared manager owns sockets/serial ports."""

import ipaddress
import os

from modbus_connection import ModbusSerialParams, ModbusTcpParams

MODES = ("tcp", "tcp_gateway", "rtu_tcp", "serial")


def params_from(data):
    mode = data["transport"]
    if mode not in MODES:
        raise ValueError("invalid_transport")
    if mode == "serial":
        path = data["device"]
        if not path.startswith("/dev/") or ".." in path.split("/"):
            raise ValueError("invalid_serial_path")
        # Resolve by-id aliases, but never allow them to escape /dev.
        path = os.path.realpath(path)
        if not path.startswith("/dev/") or os.path.commonpath(("/dev", path)) != "/dev":
            raise ValueError("invalid_resolved_serial_path")
    else:
        host = data["host"].strip().lower().rstrip(".")
        if host.startswith("[") and host.endswith("]"):
            host = host[1:-1]
        try:
            host = ipaddress.ip_address(host).compressed
        except ValueError:
            pass
        if not host or any(c.isspace() for c in host) or any(c in host for c in "/@?#"):
            raise ValueError("invalid_host")
        port = int(data["port"])
        if not 1 <= port <= 65535:
            raise ValueError("invalid_port")
        if mode != "rtu_tcp":
            return ModbusTcpParams(host=host, port=port)
        host = f"[{host}]" if ":" in host and not host.startswith("[") else host.lower()
        path = f"socket://{host}:{port}"
    baud = int(data.get("baudrate", 9600))
    parity = data.get("parity", "N")
    stopbits = int(data.get("stopbits", 1))
    if (
        baud not in (1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200)
        or parity not in ("N", "E", "O")
        or stopbits not in (1, 2)
    ):
        raise ValueError("invalid_serial_settings")
    return ModbusSerialParams(
        device=path, baudrate=baud, bytesize=8, parity=parity, stopbits=stopbits
    )


def endpoint_key(data):
    return "|".join(map(str, params_from(data).endpoint))
