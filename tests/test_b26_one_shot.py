"""FC05 one-shot lab tests using the actual library class boundary, no wire."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from custom_components.comwintop import single_attempt as one


@asynccontextmanager
async def _paced(_unit_id):
    yield


class FakeBase:
    def __init__(self, outcome=True):
        self.outcome = outcome
        self.calls = []

    async def send_and_receive(self, slave, pdu):
        self.calls.append((slave, pdu))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def setup(monkeypatch, outcome=True):
    base = FakeBase(outcome)
    transport = SimpleNamespace(
        base_transport=base,
        _communication_lock=asyncio.Lock(),
        _last_request_finished_at=None,
    )
    client = SimpleNamespace(transport=transport)
    conn = SimpleNamespace(_pacer=SimpleNamespace(paced=_paced))
    unit = SimpleNamespace(_unit_id=1)
    monkeypatch.setattr(one, "_existing_connection", lambda _: (conn, client, transport, base))
    return base, transport, unit


async def test_single_wire_call_with_pacer_guard_and_bool_ack(monkeypatch):
    base, transport, unit = setup(monkeypatch)
    recorded = []
    assert await one.fc05_once(unit, 0, True, lambda: recorded.append("guard")) is True
    assert recorded == ["guard"] and len(base.calls) == 1
    assert base.calls[0][0] == 1
    assert transport._last_request_finished_at is not None


async def test_busy_is_not_retried(monkeypatch):
    base, _, unit = setup(monkeypatch, RuntimeError("busy"))
    with pytest.raises(RuntimeError, match="busy"):
        await one.fc05_once(unit, 0, True, lambda: None)
    assert len(base.calls) == 1


async def test_unconfirmed_ack_is_rejected_without_repeating(monkeypatch):
    base, _, unit = setup(monkeypatch, False)
    with pytest.raises(ValueError, match="fc05_ack_mismatch"):
        await one.fc05_once(unit, 0, True, lambda: None)
    assert len(base.calls) == 1


async def test_no_transmission_when_guard_rejects(monkeypatch):
    base, _, unit = setup(monkeypatch)

    def refuse():
        raise RuntimeError("write_permission_revoked")

    with pytest.raises(RuntimeError, match="write_permission_revoked"):
        await one.fc05_once(unit, 0, True, refuse)
    assert not base.calls


@pytest.mark.parametrize("address,value", [(8, True), (-1, True), (0, 1)])
async def test_invalid_trajectory_never_sends(monkeypatch, address, value):
    base, _, unit = setup(monkeypatch)
    with pytest.raises(ValueError, match="unsupported_fc05"):
        await one.fc05_once(unit, address, value, lambda: None)
    assert not base.calls


async def test_readback_failure_must_be_handled_by_write_manager():
    # The low-level executor cannot mark a physical contact confirmed.
    # WriteManager handles a separate FC01 mismatch / failure.
    from custom_components.comwintop.write_manager import WriteManager, WriteRejected

    async def execute(_key, requested, guard):
        guard()
        return not requested

    manager = WriteManager(execute, lambda _key: True)
    with pytest.raises(WriteRejected, match="readback_mismatch"):
        await manager.submit("do_1", True)
    assert "do_1" in manager.blocked
    await manager.close()
