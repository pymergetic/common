from __future__ import annotations

import asyncio
import pytest


@pytest.mark.asyncio
async def test_boost_asio_async_add_bridge() -> None:
    ext = pytest.importorskip("pymergetic.common.__cpp_test__", exc_type=ImportError)
    fut = ext.boost_asio_async_add(2, 3)
    assert await fut == 5


@pytest.mark.asyncio
async def test_boost_asio_async_bridge_exception() -> None:
    ext = pytest.importorskip("pymergetic.common.__cpp_test__", exc_type=ImportError)
    with pytest.raises(RuntimeError, match="boom"):
        await ext.boost_asio_async_fail("boom")


@pytest.mark.asyncio
async def test_boost_asio_async_bridge_stress() -> None:
    ext = pytest.importorskip("pymergetic.common.__cpp_test__", exc_type=ImportError)
    # Keep this moderate to avoid flakiness in CI while still catching races.
    n = 500
    futs = [ext.boost_asio_async_add(i, i + 1) for i in range(n)]
    res = await asyncio.gather(*futs)
    assert res[0] == 1
    assert res[-1] == (n - 1) + n


