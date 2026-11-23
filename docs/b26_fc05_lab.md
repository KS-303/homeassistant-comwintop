# ComWinTop 0.1.0b26 – FC05 relay laboratory test

This is an **explicit laboratory version**. Its support is limited to
`CWT-MB307D(II)-S` (8 digital inputs, 8 digital output readbacks, 8 analog input
register reads) connected via the shared Home Assistant transparent
RTU-over-TCP gateway. The source branch is
`feature/b26-mb307d-fc05-lab`. Do not connect loads to relay contacts during
validation.

## Hardware configuration

The MB307D answered as slave **1** in Registerwerk. An address change to **3**
has been requested but has not been demonstrated; configure the actual
current slave address, not the planned one. TM-32DS remains on slave 2.

For this lab the only writable function is **FC05** (DO coils 0–7).
No FC06, FC15, FC16, AI/AO writes, automatic relays on startup, or automatic
restore from a saved state. `write_enabled` is disabled for every DO by
default. Explicitly enable only DO1 (physical **DO0**), then restart/reload
the integration to create that switch. Existing DO binary readback remains.

## Busy/retry workaround

The normal Home Assistant `unit.write_coil` calls the backend smart
transport which retries Device Busy. The b26 lab bypasses that retry *only
for FC05*, by calling the existing backend's **single** RTU base transport
exchange under the same tmodbus shared communication lock, HA pacer,
and ComWinTop hub bus lock. It does not create a competing socket/master.

Supported dependency versions are pinned to
`modbus-connection==4.12.7` and `tmodbus==1.1.0`, with exact type checks
before transmission; incompatible installations fail closed. No private
dependency patch or overwrite is installed. The internal API approach
is deliberately experimental and must be revalidated at each backend
version upgrade.

An FC01 readback is performed after writing. This confirms the module's
reported coil bit, **not the physical relay contact**. On mismatches and
unknown outcomes the channel/RTU bus is latched; commands are not replayed.
`WriteManager` also checks authorization and the command lifetime before
the single low-level attempt.

## First hardware test (no load)

1. Stop Registerwerk and any additional master using the Waveshare gateway.
2. Install the successful b26 GitHub CI ZIP, not loose source or an earlier b25.
3. Add `CWT-MB307D(II)-S` as a device with the *currently programmed*
   slave ID (1 until changed). Keep the TM32DS on slave 2.
4. Enable `write_enabled` on **do_1** alone (physical DO0).
5. Confirm FC01 readback is fresh, unit ONLINE, and no RTU repairs unresolved.
6. Click the DO0 switch ON. Check LED 0 and relay click, followed by FC01
   readback ON. Then manually click OFF and confirm LED/relay/readback OFF.
7. Only then individually enable other output channels if needed.

If a command is not confirmed, **do not click it again immediately**.
The relay may have changed despite a timeout. Check its LED, readback
and physical state. Complete explicit RTU recovery if indicated before
re-enabling writes.

## Known limitations / unverified

- This is not an electrical contact feedback test.
- No hardware test has yet proven the new b26 code actually sends exactly
  one RTU frame on the user's gateway under Busy, timeout or disconnect.
- The 2-second deadline is validated before the base transport call,
  but the internal RTU frame can be queued briefly by the backend after
  this check. This is a **lab-only exception** to the full product contract,
  and not a certification of the actual wire send timestamp.
- RTU frames have no transaction ID; another independent master sharing
  the gateway can still cause misassociation.
- The AI signal scaling is unverified. Raw values are readable; physical
  engineering-value entities remain unavailable.
- The verified outputs are DO0–7 physically; HA channel keys are do_1–do_8.
- Do not merge into the production branch or attach safety-critical loads
  until on-wire evidence has been collected and analyzed.

## Acceptance checks

GitHub Actions must pass lint, formatter, pytest, package metadata, archive
integrity and build. Hardware results must be recorded separately and not
inferred from unit tests.
