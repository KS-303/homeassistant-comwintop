# b27 – CWT-MB307D(II)-S Home Assistant relay controls

The b26 FC05 laboratory transport remains unchanged, including its narrowly
scoped single-attempt RTU-over-TCP gate, per-channel authorization, and
FC01 readback. This b27 update fixes a UI registration mistake: b26 did
not create a switch entity until `write_enabled` was already true, so
users saw only `Digitaler Ausgang ... Rückmeldung` entities.

## HA entities

For MB307D each configured and enabled DO channel now has **two**
independent Home Assistant entities:

- `binary_sensor`: read-only *Digitaler Ausgang N – Rückmeldung*, FC01.
- `switch`: *Digitaler Ausgang N – Schalten*, requesting FC05.

All eight switches are registered on first setup, even when their write
permission is off. Initially they show *unavailable* (not a writable
toggle). They become usable **only** after the individual output's
`write_enabled` permission is set, fresh FC01 data exists, the device
status is ONLINE, and the backend transport release applies. This fixes
discoverability without silently authorizing writes.

## Single-screen relay permissions

Go to **Settings → Devices & services → ComWinTop → MB307D device →
Configure → Relais-Schreibfreigaben (DO1–DO8)**.

Each of the eight flags corresponds to a physical output:

| Home Assistant channel | Hardware terminal | Function |
|---|---|---|
| do_1 | DO0 | FC05 coil address 0 |
| do_2 | DO1 | FC05 coil address 1 |
| do_3 | DO2 | FC05 coil address 2 |
| do_4 | DO3 | FC05 coil address 3 |
| do_5 | DO4 | FC05 coil address 4 |
| do_6 | DO5 | FC05 coil address 5 |
| do_7 | DO6 | FC05 coil address 6 |
| do_8 | DO7 | FC05 coil address 7 |

The form changes **permissions only**, not output states. Leave all
eight unchecked by default. For the first test check *do_1* only, save,
then check that its switch becomes available after fresh readback. Test
ON, then OFF, with the relay **disconnected from electrical loads**.
Never run Registerwerk and HA simultaneously on the same single-master
transparent RTU gateway. Disconnect Registerwerk first.

The device's last hardware-confirmed slave ID was **1** (change to 3
is not proven), TM-32DS remains on ID 2.

## Acceptance conditions

- Every MB307D DO control is registered without write permission; locked
  controls remain unavailable, no FC05 sent on setup.
- Saving a permission triggers HA config-entry reload and retains stable
  switch identity.
- A permitted DO can issue exactly one FC05 request per user action
  through the single-attempt RTU transport; normal HA FC05 retries are
  not used. FC01 must confirm the reported output bit.
- Existing MB308N and TM-32DS must remain read-only.
- A Busy, timeout, mismatch, disconnect or other uncertain write
  is not replayed. The RTU safety guard can require manual recovery.

**This is a hardware laboratory version, not a certified production
controller.** Do not attach loads for the initial test. Relay readback is
not an independent physical contact measurement.
