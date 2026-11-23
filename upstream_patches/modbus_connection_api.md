# Proposed modbus-connection API reference

The backend-neutral `ModbusUnit` Protocol adds keyword-only
`retry: bool = True` to `write_coil`, `write_register`, `write_coils`, and
`write_registers`. Existing callers keep the current behavior.

```python
unit = async_get_unit(hass, entry, params, unit_id)
await unit.write_register(16, 0x0204, retry=False)
```

The tmodbus adapter delegates the flag to the matching tmodbus write method.
The pymodbus adapter constructs its clients with `retries=0`. For an explicit
`retry=False` request, it also checks the instantiated transaction retry
count immediately before calling the write. If the count is unavailable or
nonzero, it raises `ModbusError` without sending. The adapter uses a
read-only property of its owned pymodbus client; an upstream public
capability accessor would make this guarantee less version dependent.

`retry=False` means at most one attempt from the tested software transport.
It does not ensure exactly one execution by a remote unit. A timeout,
disconnect, or cancellation can leave the outcome uncertain. Callers must
read back the state and avoid automatic resubmission. This flag does not
implement an output-command expiry deadline.
