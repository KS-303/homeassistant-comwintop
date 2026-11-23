"""Priority bus lock ensures writes precede queued read polls safely."""

import asyncio

import pytest

from custom_components.comwintop.bus_priority import PriorityBusLock
from custom_components.comwintop.write_manager import WriteManager, WriteRejected


async def spin():
    for _ in range(5):
        await asyncio.sleep(0)


async def test_write_goes_before_queued_reads_after_in_flight_read_completes():
    bus = PriorityBusLock()
    started = asyncio.Event()
    release = asyncio.Event()
    trace = []

    async def first_read():
        async with bus:
            trace.append("read1")
            started.set()
            await release.wait()

    async def next_read():
        async with bus:
            trace.append("read2")

    async def write():
        async with bus.writer():
            trace.append("FC05")

    reader1 = asyncio.create_task(first_read())
    await started.wait()
    reader2 = asyncio.create_task(next_read())
    await spin()
    writer = asyncio.create_task(write())
    await spin()
    release.set()
    await asyncio.wait_for(asyncio.gather(reader1, reader2, writer), 1)
    assert trace == ["read1", "FC05", "read2"]


async def test_cancelled_pending_writer_does_not_starve_reads():
    bus = PriorityBusLock()
    release = asyncio.Event()
    acquired = asyncio.Event()

    async def first_read():
        async with bus:
            acquired.set()
            await release.wait()

    task = asyncio.create_task(first_read())
    await acquired.wait()
    writer = asyncio.create_task(bus.writer().__aenter__())
    await spin()
    reader_done = asyncio.Event()

    async def queued_read():
        async with bus:
            reader_done.set()

    reader = asyncio.create_task(queued_read())
    await spin()
    writer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await writer
    release.set()
    await asyncio.wait_for(reader_done.wait(), 1)
    await asyncio.gather(task, reader)
    assert bus._waiting_writers == 0


async def test_failing_writer_releases_lock_for_read_poll():
    bus = PriorityBusLock()
    with pytest.raises(ValueError, match="expected"):
        async with bus.writer():
            raise ValueError("expected")
    async with asyncio.timeout(1):
        async with bus:
            pass


async def test_write_manager_deadline_still_checked_when_writer_gets_lock():
    bus = PriorityBusLock()
    read_ready = asyncio.Event()
    release_read = asyncio.Event()
    clock = [0.0]
    physical_writes = []

    async def hold_read():
        async with bus:
            read_ready.set()
            await release_read.wait()

    async def execute(_key, value, guard):
        async with bus.writer():
            guard()
            physical_writes.append(value)
            return value

    reader = asyncio.create_task(hold_read())
    await read_ready.wait()
    manager = WriteManager(execute, lambda _key: True, clock=lambda: clock[0])
    command = asyncio.create_task(manager.submit("do_1", True))
    await spin()
    clock[0] = 2.1
    release_read.set()
    with pytest.raises(WriteRejected, match="expired"):
        await asyncio.wait_for(command, 1)
    await reader
    assert physical_writes == []
    await manager.close()


async def test_writer_is_not_blocked_by_unrelated_queued_reader_when_bus_frees():
    bus = PriorityBusLock()
    owner_ready = asyncio.Event()
    owner_release = asyncio.Event()
    write_called = asyncio.Event()
    read_called = asyncio.Event()

    async def current():
        async with bus:
            owner_ready.set()
            await owner_release.wait()

    async def followup_read():
        async with bus:
            read_called.set()

    async def command():
        async with bus.writer():
            write_called.set()

    owner = asyncio.create_task(current())
    await owner_ready.wait()
    reader = asyncio.create_task(followup_read())
    await spin()
    writer = asyncio.create_task(command())
    await spin()
    owner_release.set()
    await asyncio.wait_for(write_called.wait(), 1)
    await asyncio.gather(owner, reader, writer)
    assert read_called.is_set()
