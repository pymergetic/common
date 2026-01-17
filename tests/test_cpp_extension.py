from __future__ import annotations

import pytest

def test_common_cpp_extension_smoke() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)
    assert ext.add(2, 3) == 5


def test_common_cpp_extension_boost_asio_smoke() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)
    assert ext.boost_asio_timer_fires() is True


def test_common_cpp_extension_optional_support() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)
    o = ext.NativeOptional()
    assert o.name is None
    o.name = "x"
    assert o.name == "x"


def test_common_cpp_extension_native_address_view_is_live() -> None:
    """Ensure our nanobind container view behaves like a live C++ container."""

    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)
    native = ext.make_native_peer_nested()

    assert len(native.addresses) == 2
    assert native.addresses[0].ip == "10.0.0.1"

    a = ext.NativeAddress()
    a.ip = "10.0.0.3"
    native.addresses.append(a)
    assert len(native.addresses) == 3
    assert native.addresses[2].ip == "10.0.0.3"

    native.addresses.erase(1)
    assert len(native.addresses) == 2
    assert [native.addresses[i].ip for i in range(len(native.addresses))] == ["10.0.0.1", "10.0.0.3"]


def test_common_cpp_extension_shared_ptr_payload_smoke() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)
    pkt = ext.make_network_packet()
    assert pkt.id == "pkt-1"
    assert pkt.timestamp == 1.0
    assert pkt.payload.size() == 1024


