from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_boost_asio_async_add_bridge() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)
    fut = ext.boost_asio_async_add(2, 3)
    assert await fut == 5


