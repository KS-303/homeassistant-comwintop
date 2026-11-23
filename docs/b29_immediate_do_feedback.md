# b29 – Immediate FC01 feedback and one in-flight command per relay

Laborversion for CWT-MB307D(II)-S, RTU over TCP only. Remains limited
to manually enabled FC05 output coils 0–7 and hardware unloaded tests.
DO readback is the module's coil bit, **not** a separate physical contact sensor.

## Changes from b28

- FC05 remains a single non-retrying transmission using the shared RTU link.
- A valid FC01 readback is immediately copied into the same channel's
  Home Assistant sample and a coordinator update is published. The
  regular group poll interval (typically 8 seconds for a newly added
  MB307D) is *not* shortened. Confirmed HA feedback does not wait for
  that next periodic poll.
- A second ON/OFF request for the **same** DO while any earlier request
  is pending, transmitting, or still being confirmed is rejected with
  `write_in_progress`. No queue, no supersession, no repeated FC05.
  Home Assistant reports a clear localized error instead of a generic
  unqualified communication error. Other outputs remain independently
  authorized but still share the serial bus.
- Two-second pre-send TTL, one-second inter-frame bus spacing,
  single-attempt FC05 timeout and four-second FC01 readback deadline
  remain in place.
- A valid FC01 that disagrees with the desired state is displayed as
  the *actual reported coil state*, while the WriteManager still
  rejects the command and quarantines that channel. Do not assume a
  mechanical relay contact follows the bit.
- No automatic restoration/replay after Busy, timeout, disconnect,
  repair, or Home Assistant restart.

## Hardware test

1. Disconnect Registerwerk (no competing Modbus masters).
2. Leave all relay contacts without attached load.
3. Test physical DO0 with only `do_1` enabled for FC05.
4. Press ON once; confirm coil readback in HA changes without waiting
   for the next configured DO polling interval.
5. Press OFF once after confirmation; verify LED and FC01.
6. Trigger a second click **while the first command is pending**.
   Expected: "Schaltvorgang läuft bereits" (or English equivalent)
   without any extra FC05 and without bus-level RTU repair prompt.
7. If any actual FC05/FC01 outcome is uncertain, stop; inspect the
   relay and diagnostics before attempting another command.

Automated CI checks cannot substitute for testing timing on the actual
Waveshare gateway.

## Confirmed behavior in HA, 23 November 2026

During rapid manual clicks, Home Assistant displayed:

> Die Aktion switch/turn_off konnte nicht ausgeführt werden.
> Schaltvorgang läuft bereits. Bitte erst die Rückmeldung abwarten.

This is the intended `write_in_progress` protection: a second command
to the same relay is rejected while the first is pending or being
confirmed. This observation alone does **not** establish the duration
of the first command, successful FC01 confirmation, or a wire-frame count.

## Binding rule for future Home Assistant automations

**Switching is a transaction, not an instantaneous state assignment.**

1. Check the relay's separate FC01 readback entity and device/bus quality
   before issuing a command. Skip commands when the confirmed target
   state is already present.
2. Send **one** `switch.turn_on` / `switch.turn_off` request per relay.
   Never use rapid duplicate service calls or delayed blind retries.
3. Wait for a **fresh FC01 readback matching the requested state**, not
   merely for the HA service call to return or for a fixed sleep timer.
   After b29 this readback is normally published immediately once received.
4. Apply a bounded automation timeout and handle timeout, unavailable,
   `write_in_progress`, `write_locked`, mismatch, and RTU bus repair
   states explicitly. On uncertain completion, **do not auto-resend**;
   check physical relay status before any manual recovery.
5. Prevent overlapping automation executions controlling the same DO
   (e.g. HA automation `mode: single` where appropriate). Never use a
   queued run mode to build up stale opposite relay requests.
6. Respect one-second message spacing on the shared link and the
   two-second pre-transmission command TTL. Those are transport bounds,
   **not** a guarantee of total end-to-end command duration.
7. FC01 reports the module's coil state, **not independently verified
   mechanical contact closure**. Safety-critical load feedback needs
   separate electrical feedback hardware.

This is a design and acceptance requirement for later automation work;
no automation should be deployed until its sequencing and timeout cases
have been tested on the physical gateway.
