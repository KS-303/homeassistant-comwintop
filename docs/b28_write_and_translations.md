# b28 – Laboratory FC05 fault handling and German UI

This changes no Modbus address or supported hardware profile. It is still
limited to the **CWT-MB307D(II)-S** on the shared transparent RTU/TCP
gateway. All writes remain per-channel opt-in; this is not production
certification.

## Actual hardware evidence (23 November 2026)

The user operated a Home Assistant relay control. The physical relay
energized, and Home Assistant briefly reflected the output, but it then
raised **"RTU-Bus gesperrt – Hardwareprüfung erforderlich"**. After
manual repair confirmation it recovered with perceptible delay.
The recording shows switches and readbacks, but **not raw RTU wire traces**.
Therefore it does not prove whether the failure was at FC05 ACK, subsequent
FC01 readback, a transport callback, or a timeout while waiting on the bus.

## b28 changes

- The FC05 write path records a stage and duration:
  `waiting_for_bus`, `fc05_preflight`, `fc01_readback`, `confirmed`,
  `rejected_before_send`.
- A known pre-transmission rejection (`WriteRejected`, incompatible backend,
  stale authorization, no connection) **does not latch** the RTU bus. A
  cancellation while still waiting on the local bus lock also doesn't.
- A potentially transmitted but not confirmed FC05 **still latches**; the
  repair code distinguishes `write_fc05_unconfirmed` from
  `write_readback_unconfirmed`. No automatic retry or replay is introduced.
- The FC01 readback retains the original 4-second request deadline,
  which already includes pacing; no artificial extra switching delay.
  This is not a blanket recovery or guaranteed low latency.
- Privacy-safe diagnostic fields (no register values, names, IPs or
  tokens): `last_write_phase`, `last_write_duration_ms`,
  `last_write_error`. Also exposed as attributes on the control entity.
- Relay checkbox labels are localized directly in the HA flow. Internally,
  stable keys `do_1`–`do_8` remain unchanged, and changing the
  permission form never issues an FC05.
- Relay/analog raw display labels follow HA language. Cross-language
  translation key parity is enforced by regression tests across
  `strings.json`, `translations/en.json`, and `translations/de.json`.

## Hardware retest: first DO0 only

1. Ensure no external load is connected and Registerwerk is disconnected.
2. Install the CI-tested b28 ZIP, keep actual slave ID (last confirmed **1**).
3. In the MB307D config select **Relais-Schreibfreigaben** and allow only
   physical DO0 (form: Ausgang 1).
4. Check FC01 DO0 readback and bus status ONLINE before action.
5. Press ON only once, check relay LED and coil readback. Then OFF only
   once if the bus remains healthy.
6. If there is a repair request, don't retry blindly. Export diagnostics
   while the error is still present and record the values of
   `last_write_phase`, `last_write_duration_ms`, `last_write_error`
   and `rtu_bus_unsafe_reason`. Those distinguish transmission vs
   readback failure. Inspect physical relay state before manual reset.
7. Only consider enabling other outputs after DO0 has completed repeatedly
   without a repair latch.

This change prevents false bus safety alarms for commands definitely never
transmitted. It does **not** claim to fix a genuine device-side lost
reply nor prove the laboratory transport on the physical gateway.
