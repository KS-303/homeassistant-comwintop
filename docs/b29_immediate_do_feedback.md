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
