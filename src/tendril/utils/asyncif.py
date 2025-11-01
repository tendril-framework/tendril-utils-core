
import asyncio
import inspect
import threading
from concurrent.futures import ThreadPoolExecutor


# ---------------------------------------------------------------------
# Per-thread event loop reuse
# ---------------------------------------------------------------------
_local = threading.local()


class AsyncLoopContext:
    """
    Context manager that provides a reusable asyncio event loop
    for all async executions within the same thread.

    Example:
        with AsyncLoopContext():
            val1 = run_callable_blocking(async_func1)
            val2 = run_callable_blocking(async_func2)
            # both reuse the same loop
    """

    def __enter__(self):
        if getattr(_local, "loop", None):
            raise RuntimeError("AsyncLoopContext already active in this thread")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _local.loop = loop
        return loop

    def __exit__(self, exc_type, exc_val, exc_tb):
        loop = getattr(_local, "loop", None)
        if loop:
            try:
                loop.close()
            finally:
                _local.loop = None
                asyncio.set_event_loop(None)


def run_callable_blocking(func, *args, **kwargs):
    """
    Execute a callable (sync or async) and block until result is available.

    - Sync functions run directly.
    - Async functions run in:
        * an existing AsyncLoopContext (if active),
        * or a temporary loop (if no loop and no active context),
        * or a background thread if already inside a running loop.

    Automatically reuses a per-thread loop if available.
    """
    if not callable(func):
        raise TypeError(f"Expected callable, got {type(func).__name__}")

    result = func(*args, **kwargs)

    if not inspect.isawaitable(result):
        return result

    # Case 1: Reuse active per-thread loop
    existing_loop = getattr(_local, "loop", None)
    if existing_loop:
        return existing_loop.run_until_complete(result)

    # Case 2: Already inside another running loop (e.g. FastAPI)
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop:
        def _runner(coro):
            inner_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(inner_loop)
            try:
                return inner_loop.run_until_complete(coro)
            finally:
                asyncio.set_event_loop(None)
                inner_loop.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_runner, result)
            return future.result()

    # Case 3: No loop at all — create temporary
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(result)
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def run_callable_async(func, *args, **kwargs):
    """
    Execute a callable (sync or async) and return an awaitable result.

    - Async callables are awaited directly.
    - Sync callables are executed in a threadpool to avoid blocking.
    """
    if not callable(func):
        raise TypeError(f"Expected callable, got {type(func).__name__}")

    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

