# b30 – MB307D write priority under cyclic wave testing

## Evidence from Home Assistant hardware test (2026-11-23)

The user's "all outputs ON, then all outputs OFF" test sent ON
requests to DO0–DO5 in sequence with FC01 confirmations. At 15:46:23,
the request for physical DO6 (HA `do_7`) was rejected with
"Schaltauftrag abgelaufen, bevor er gesendet werden konnte".

**Interpretation:** The two-second `WRITE_TTL` expired before the
one-shot FC05 send guard. By design an expired command is not sent,
and no RTU repair latch is needed. This is not proof of a lost
connection or relay hardware fault. Multiple ComWinTop devices and
their background reads share the same one-second-paced bus.

The automation stopped during the ON wave. Outputs DO0–DO5 may remain
energized; no unconditional automatic OFF is permitted on an unknown
state. Physically verify those relays and their FC01 readbacks before
another test.

## What changes

All coordinators on the same ComWinTop config entry now use a single
`PriorityBusLock` instead of the previous FIFO-ish `asyncio.Lock`.
A new write request gives its FC05+FC01 transaction priority over
**queued future ComWinTop polls**. Existing in-flight reads are
allowed to finish before any write begins. After a write is done,
reads resume. Cancellation of a queued writer wakes the readers
so no read starvation occurs.

This does **not** preempt an active read, interrupt a Modbus frame,
bypass a hardware safety guard, or take precedence over traffic from
unrelated Home Assistant integrations sharing the underlying backend.
The transport's real one-second message spacing remains enforced.
`WRITE_TTL=2.0` remains enforced at the send boundary; a write
that cannot safely start inside that window is still rejected.
Neither expired nor ambiguous writes are automatically retried.

## Acceptance criteria and safety

- Verify 8 ON operations in ascending order with immediate FC01
  readback on each channel, then 8 OFF operations, without losing
  the connection or replaying a stale command.
- Check an existing read completes before a queued write is admitted.
- Check queued read polling yields to an awaiting write.
- Check a cancelled queued write does not deadlock reads or send FC05.
- Confirm actual TTL expiration continues to fail closed with no write.
- Verify polling on TM-32DS resumes while MB307D is not writing.
- Do not interpret a coil readback as independent mechanical-contact
  status. The test must be performed without loads connected.

**Hardware outcome is pending**; CI alone cannot guarantee every
write will fit within 2 seconds on the actual RTU/TCP gateway.
