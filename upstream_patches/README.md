# Separate upstream prototype (not installed in Home Assistant)

These are review drafts against **tmodbus 1.1.0** and
**modbus-connection 4.12.7**. No upstream pull request has been opened.
Do not copy either patch into a production HA instance. Applying both to
isolated copies is required; applying only the wrapper patch is insufficient.
Proposed public documentation accompanies each patch:
[tmodbus API](tmodbus_api.md) and
[modbus-connection API](modbus_connection_api.md). Upstream maintainers must
place these explanations into their README and reference pages as required.

API proposal: `ModbusUnit.write_register(..., retry=False)` and the matching
FC05/FC15/FC16 methods forward the opt-in flag through `AsyncModbusClient`.
`AsyncSmartTransport.send_and_receive_once` takes its existing communication
lock and calls the one-attempt transport method, bypassing the combined
response/Busy/reconnect retry strategy. The ordinary path and default
`retry=True` retain their current behavior. Unsupported custom transports
raise `NotImplementedError` for the opt-in instead of silently retrying.
The pymodbus adapter accepts the flag and constructs clients with
`retries=0`. With `retry=False`, it checks the actual transaction retry
count before calling the write method. Missing or nonzero counts raise a
neutral Modbus error. A test forces retries=2 and checks that all four
writes fail closed with zero wire frames. This read-only check of the
adapter-owned client is not a stable pymodbus public contract; maintainers
should review it or provide an upstream accessor.

The prototype was tested by copying the two installed packages into a
temporary directory, applying the patches only to those copies, and running
`PYTHONPATH=<patched-copy>:<repo> python upstream_patches/wire_check.py`.
The script uses an independent TCP/RTU-over-TCP simulator and checks actual
request frames, not method-call counts. It must be run explicitly; the normal
ComWinTop CI continues to test the unmodified production dependencies.
Run `upstream_patches/pty_check.py` with the same patched-copy environment
for Linux serial PTY tests on both backends. The patch paths are rooted at
each upstream repository's `src/` directory and pass `git apply --check`
against the pinned source snapshots.

The public write API accepts keyword-only `retry: bool = True`. The default
preserves existing calls. `retry=False` covers transport retries, but does
not check the separate 2-second ComWinTop DO/AO command deadline at the
actual send boundary. Manual L-51a setup has its own confirmation and
verification flow; the output-command TTL is not its blocker. Neither
patch alone is ready to enable production writes.

Before upstream adoption, add these cases to each project's own CI, test
the deadline at the physical send boundary and a real HA process restart,
and review all custom transport implementations. Both upstreams require
human review of AI-assisted work and prohibit autonomous external PRs;
tmodbus additionally asks contributors to discuss the change first.
The files here are a proposal, not a release artifact.
