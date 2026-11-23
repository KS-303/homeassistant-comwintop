# b25 – CWT-MB307D(II)-S hardware profile and write preparation

**Development branch:** `feature/b25-mb307d-write-preparation`, based on b24.
**Not a production release.** Existing b24 deployments stay read-only.

## Hardware verification, 23 November 2026

Tested via Registerwerk 0.3.0 and a Waveshare ETH-RS485 gateway on the
same physical bus as the TM-32DS. At test time the MB307D was slave 1;
the planned change to slave 3 has **not** yet been confirmed.

| Group | FC | Zero-based addresses | Evidence | Limits |
|---|---|---|---|---|
| DI0–7 | 02 | 0–7 | Eight independent 12 V transitions 0→1→0 | Input polarity verified with correct DI COM wiring |
| DO0–7 | 01 | 0–7 | Eight readable output states | Status readback is **not** independent physical contact feedback |
| DO0–7 | 05 | 0–7 | Relay ON/OFF, audible clicks/LEDs, FC01 verification | No third-party load attached; no electrical contact measurement |
| AI0–7 | 03 | 50–57 | Eight accepted read frames, each raw zero | No signal injection; range/scale/unit unverified |

FC03 address 16 returns Modbus Exception 02 on this model.
**Do not reuse the TM-32DS slave-address register or issue an FC06 write
to an undocumented configuration address.**

## b25 implementation

- Builtin model `mb_307d_ii_s` with 8 DI, 8 DO readbacks and 8 AI raw reads.
- AI physical states deliberately remain unavailable until a known input
  signal validates scale and engineering units.
- `write_enabled` can be configured *per digital output* (off by default).
  This is only a persisted permission, **not** permission to transmit.
- The switch entity and the existing WriteManager are connected in code,
  but the hard transport-release set remains empty: no b25 FC05 writes
  can leave Home Assistant.
- Changes to slave address, disabling a channel, or consequential output
  configuration changes revoke explicit write permissions.
- No automatic output restoration on restart or reconnection.

## Why the b25 switch remains closed

The installed unmodified Home Assistant `modbus-connection` /
`tmodbus` backend has previously been observed retrying FC05 after
Modbus Exception 06 (Device Busy), even when callers expected no retries.
Upstream `retry=False` patches in this repository are proposals, **not**
part of the installed HA dependency. Also, the 2-second command deadline
must be checked at the actual transport send boundary, not merely before
awaiting a shared-unit method that may queue.

The MB307D hardware test proves FC05 works in **Registerwerk**.
It does **not** prove no-retry semantics for the Home Assistant backend.

Before adding a value to `HARDWARE_VALIDATED_WRITES`:

1. Adopt and test a stable public no-retry path for FC05, FC06, FC15, FC16.
2. Instrument on-wire traces for success, Busy, timeout, disconnect,
   cancellation and concurrent readers, through this exact gateway.
3. Enforce deadline and authorization at the actual transmission boundary
   while holding shared bus ownership.
4. Confirm relay readback, mismatch quarantine, slave-local recovery,
   persistence across unclean HA restarts and no stale command replay.
5. Run automated HA CI and a distinct hardware test **without live loads**.

This work cannot truthfully be marked hardware-write-certified until
those steps pass. Toggle `write_enabled` to prepare one channel, but do
not expect a working switch or change the release gate manually.
