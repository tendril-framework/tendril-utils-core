
import asyncio
import threading
import time
import pytest

from tendril.utils.asyncif import (
    run_callable_blocking,
    run_callable_async,
    AsyncLoopContext,
)

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def sync_add(a, b):
    """Simple synchronous callable."""
    time.sleep(0.05)
    return a + b


async def async_add(a, b):
    """Simple async callable."""
    await asyncio.sleep(0.05)
    return a + b


def sync_raises():
    """Synchronous callable that raises."""
    raise ValueError("sync error")


async def async_raises():
    """Async callable that raises."""
    await asyncio.sleep(0.01)
    raise ValueError("async error")


# ---------------------------------------------------------------------
# Blocking execution tests
# ---------------------------------------------------------------------

def test_run_callable_blocking_sync_function():
    result = run_callable_blocking(sync_add, 2, 3)
    assert result == 5


def test_run_callable_blocking_async_function():
    result = run_callable_blocking(async_add, 2, 3)
    assert result == 5


def test_run_callable_blocking_error_sync():
    with pytest.raises(ValueError, match="sync error"):
        run_callable_blocking(sync_raises)


def test_run_callable_blocking_error_async():
    with pytest.raises(ValueError, match="async error"):
        run_callable_blocking(async_raises)


def test_run_callable_blocking_reuses_context_loop():
    """Ensure AsyncLoopContext reuses a single loop."""
    with AsyncLoopContext() as loop:
        loop_id = id(loop)
        r1 = run_callable_blocking(async_add, 1, 1)
        r2 = run_callable_blocking(async_add, 2, 2)
        assert r1 == 2 and r2 == 4
        assert id(asyncio.get_event_loop()) == loop_id


def test_run_callable_blocking_context_loop_closed():
    """Ensure context closes the loop."""
    with AsyncLoopContext() as loop:
        run_callable_blocking(async_add, 1, 2)
    with pytest.raises(RuntimeError):
        asyncio.get_event_loop()  # no active loop now


def test_run_callable_blocking_threadsafe_execution():
    """Ensure async functions can run from multiple threads safely."""
    results = []

    def worker(x):
        res = run_callable_blocking(async_add, x, 1)
        results.append(res)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [i + 1 for i in range(5)]


def test_run_callable_blocking_inside_running_loop():
    """Ensure it runs async callable from inside another running loop."""
    async def inner():
        # Call blocking wrapper from within async context
        return run_callable_blocking(async_add, 3, 4)

    result = asyncio.run(inner())
    assert result == 7


# ---------------------------------------------------------------------
# Async execution tests
# ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_callable_async_with_async_function():
    result = await run_callable_async(async_add, 2, 3)
    assert result == 5


@pytest.mark.asyncio
async def test_run_callable_async_with_sync_function():
    result = await run_callable_async(sync_add, 3, 2)
    assert result == 5


@pytest.mark.asyncio
async def test_run_callable_async_error_sync():
    with pytest.raises(ValueError, match="sync error"):
        await run_callable_async(sync_raises)


@pytest.mark.asyncio
async def test_run_callable_async_error_async():
    with pytest.raises(ValueError, match="async error"):
        await run_callable_async(async_raises)


@pytest.mark.asyncio
async def test_run_callable_async_does_not_block_event_loop():
    """Ensure that sync functions offload properly without blocking."""
    start = time.time()

    # Run two sync tasks concurrently; should not add up linearly
    t1 = asyncio.create_task(run_callable_async(sync_add, 1, 2))
    t2 = asyncio.create_task(run_callable_async(sync_add, 2, 3))
    r1, r2 = await asyncio.gather(t1, t2)

    elapsed = time.time() - start
    assert r1 == 3 and r2 == 5
    # both ran concurrently, so elapsed < 0.1 (not 0.1 + 0.1)
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_run_callable_async_with_event_loop_running():
    """Ensure async version works inside an active event loop."""
    result = await run_callable_async(async_add, 5, 10)
    assert result == 15
