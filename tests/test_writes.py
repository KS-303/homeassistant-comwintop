import asyncio

import pytest

from custom_components.comwintop.const import HARDWARE_VALIDATED_WRITES
from custom_components.comwintop.write_manager import WriteManager, WriteRejected


async def spin():
    for _ in range(5):
        await asyncio.sleep(0)


def test_only_lab_profile_is_released():
    assert HARDWARE_VALIDATED_WRITES == frozenset({("mb_307d_ii_s", "rtu_tcp", "fc05")})


async def test_latest_pending_wins():
    ready = asyncio.Event()
    trace = []

    async def execute(key, value, guard):
        guard()
        trace.append(value)
        if len(trace) == 1:
            await ready.wait()
        return value

    m = WriteManager(execute, lambda key: True)
    first = asyncio.create_task(m.submit("do_1", True))
    await spin()
    old = asyncio.create_task(m.submit("do_1", False))
    await spin()
    new = asyncio.create_task(m.submit("do_1", True))
    await spin()
    with pytest.raises(WriteRejected, match="superseded"):
        await old
    ready.set()
    assert await first is True
    assert await new is True
    assert trace == [True, True]
    await m.close()


async def test_deadline_checked_at_send_not_dequeue():
    clock = [0]
    gate = asyncio.Event()
    sent = []

    async def execute(key, value, guard):
        await gate.wait()
        guard()
        sent.append(value)
        return value

    m = WriteManager(execute, lambda k: True, clock=lambda: clock[0])
    task = asyncio.create_task(m.submit("do_1", True))
    await spin()
    clock[0] = 2
    gate.set()
    with pytest.raises(WriteRejected, match="expired"):
        await task
    assert not sent
    await m.close()


async def test_unknown_write_drops_all_unit_pending_no_replay():
    gate = asyncio.Event()
    lock = asyncio.Lock()
    sent = []

    async def execute(key, value, guard):
        async with lock:
            guard()
            sent.append((key, value))
            await gate.wait()
            raise TimeoutError

    m = WriteManager(execute, lambda k: True)
    first = asyncio.create_task(m.submit("do_1", True))
    await spin()
    second = asyncio.create_task(m.submit("do_1", False))
    neighbor = asyncio.create_task(m.submit("do_2", True))
    await spin()
    gate.set()
    for t in (first, second, neighbor):
        with pytest.raises(WriteRejected):
            await t
    assert sent == [("do_1", True)]
    with pytest.raises(WriteRejected):
        await m.submit("do_3", True)
    m.recovered()
    await spin()
    assert len(sent) == 1
    await m.close()


async def test_mismatch_locks_channel_not_whole_unit():
    async def execute(key, value, guard):
        guard()
        return not value if key == "do_1" else value

    m = WriteManager(execute, lambda k: True)
    with pytest.raises(WriteRejected, match="readback_mismatch"):
        await m.submit("do_1", True)
    with pytest.raises(WriteRejected, match="write_locked"):
        await m.submit("do_1", False)
    assert await m.submit("do_2", True) is True
    m.channel_recovered("do_1")
    assert "do_1" not in m.blocked
    await m.close()


async def test_permission_revoked_before_transmission():
    gate = asyncio.Event()
    sent = []

    async def execute(key, value, guard):
        await gate.wait()
        guard()
        sent.append(value)
        return value

    m = WriteManager(execute, lambda k: True)
    task = asyncio.create_task(m.submit("do_1", True))
    await spin()
    m.revoke("do_1")
    gate.set()
    with pytest.raises(WriteRejected):
        await task
    assert sent == []
    await m.close()


async def test_caller_cancel_before_send_does_not_write():
    gate = asyncio.Event()
    sent = []

    async def execute(key, value, guard):
        await gate.wait()
        guard()
        sent.append(value)
        return value

    m = WriteManager(execute, lambda k: True)
    task = asyncio.create_task(m.submit("do_1", True))
    await spin()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    gate.set()
    await spin()
    assert not sent
    await m.close()


async def test_close_cleans_tasks_and_pending():
    gate = asyncio.Event()

    async def execute(key, value, guard):
        guard()
        await gate.wait()
        return value

    m = WriteManager(execute, lambda k: True)
    task = asyncio.create_task(m.submit("do_1", True))
    await spin()
    await m.close()
    with pytest.raises(WriteRejected, match="unloaded"):
        await task
    assert not m.tasks and not m.pending
    assert m.status["do_1"] == "UNCONFIRMED"
