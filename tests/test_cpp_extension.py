from __future__ import annotations

import pytest


def test_common_cpp_extension_smoke() -> None:
    # This test is only meaningful when the common wheel is built with the native extension.
    ext = pytest.importorskip("pymergetic.common._test_internal")

    assert ext.add(2, 3) == 5

    p = ext.NativePeerInfo()
    p.peer_id = "p1"
    p.addresses = ["a", "b"]

    assert p.peer_id == "p1"
    assert p.addresses == ["a", "b"]


