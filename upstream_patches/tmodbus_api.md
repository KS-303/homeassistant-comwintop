# Proposed tmodbus API reference

For `AsyncModbusClient.write_single_coil`, `write_single_register`,
`write_multiple_coils`, and `write_multiple_registers`:

```python
await client.write_single_register(16, 0x0204, retry=False)
```

`retry` is keyword-only and defaults to `True`. The default retains the
configured response, Busy and reconnect retry behavior. `False` chooses
`AsyncSmartTransport.send_and_receive_once`, which holds the same
communication lock and performs one transport call. An unsupported custom
transport raises `NotImplementedError`. The exception from an unsuccessful
request does not determine whether the device applied the write.

This option is available only on the four listed write operations. FC22,
FC23 and other write-like operations need separate review before claiming
single-attempt semantics. Cancellation after the first send has an unknown
device outcome. The option does not check an application deadline.
