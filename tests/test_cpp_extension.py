from __future__ import annotations

import pytest

from pymergetic.common.pydantic import CppModel, cpp_model


def test_common_cpp_extension_smoke() -> None:
    # This test is only meaningful when the common wheel is built with the native extension.
    ext = pytest.importorskip("pymergetic.common._test_internal")

    assert ext.add(2, 3) == 5

    p = ext.NativePeerInfo()
    p.peer_id = "p1"
    p.addresses = ["a", "b"]

    assert p.peer_id == "p1"
    assert p.addresses == ["a", "b"]


def test_common_cpp_extension_optional_support() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    o = ext.NativeOptional()
    assert o.name is None

    o.name = "x"
    assert o.name == "x"


def test_common_cpp_extension_nested_cppmodel_validation() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    # These models validate a *real* nanobind C++ object graph:
    # NativePeerNested(peer_id, main_address: NativeAddress, addresses: vector[NativeAddress]).
    @cpp_model("pymergetic.common._test_internal.NativeAddress")
    class AddressModel(CppModel):
        ip: str

    @cpp_model("pymergetic.common._test_internal.NativePeerNested")
    class PeerModel(CppModel):
        peer_id: str
        main_address: AddressModel
        addresses: list[AddressModel]

    native = ext.make_native_peer_nested()
    model = PeerModel.model_validate(native)

    assert model.peer_id == "QmHash"
    assert model.main_address.ip == "127.0.0.1"
    assert [a.ip for a in model.addresses] == ["10.0.0.1", "10.0.0.2"]


def test_common_cpp_extension_nested_write_through() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    @cpp_model("pymergetic.common._test_internal.NativeAddress", validate="lazy")
    class AddressModel(CppModel):
        ip: str

    @cpp_model("pymergetic.common._test_internal.NativePeerNested", validate="lazy")
    class PeerModel(CppModel):
        peer_id: str
        main_address: AddressModel
        addresses: list[AddressModel]

    native = ext.make_native_peer_nested()
    model = PeerModel.from_cpp(native)

    # Mutations on the model should write through to the native object.
    model.peer_id = "NewPeer"
    model.main_address.ip = "1.1.1.1"
    model.addresses[0].ip = "10.9.9.9"

    assert native.peer_id == "NewPeer"
    assert native.main_address.ip == "1.1.1.1"
    assert [native.addresses[i].ip for i in range(len(native.addresses))] == ["10.9.9.9", "10.0.0.2"]


def test_common_cpp_extension_list_append_syncs_native() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    @cpp_model("pymergetic.common._test_internal.NativeAddress", validate="lazy")
    class AddressModel(CppModel):
        ip: str

    @cpp_model("pymergetic.common._test_internal.NativePeerNested", validate="lazy")
    class PeerModel(CppModel):
        peer_id: str
        main_address: AddressModel
        addresses: list[AddressModel]

    native = ext.make_native_peer_nested()
    model = PeerModel.from_cpp(native)

    model.addresses.append(AddressModel(ip="10.0.0.3"))
    assert [native.addresses[i].ip for i in range(len(native.addresses))] == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]


def test_common_cpp_extension_list_delete_syncs_native() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    @cpp_model("pymergetic.common._test_internal.NativeAddress", validate="lazy")
    class AddressModel(CppModel):
        ip: str

    @cpp_model("pymergetic.common._test_internal.NativePeerNested", validate="lazy")
    class PeerModel(CppModel):
        peer_id: str
        main_address: AddressModel
        addresses: list[AddressModel]

    native = ext.make_native_peer_nested()
    model = PeerModel.from_cpp(native)

    del model.addresses[0]
    assert [native.addresses[i].ip for i in range(len(native.addresses))] == ["10.0.0.2"]


def test_common_cpp_extension_to_cpp_roundtrip() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    @cpp_model("pymergetic.common._test_internal.NativeAddress", validate="lazy")
    class AddressModel(CppModel):
        ip: str

    @cpp_model("pymergetic.common._test_internal.NativePeerNested", validate="lazy")
    class PeerModel(CppModel):
        peer_id: str
        main_address: AddressModel
        addresses: list[AddressModel]

    m = PeerModel(
        peer_id="P",
        main_address=AddressModel(ip="127.0.0.1"),
        addresses=[AddressModel(ip="10.0.0.1")],
    )
    native = m.to_cpp()

    assert native.peer_id == "P"
    assert native.main_address.ip == "127.0.0.1"
    assert [native.addresses[i].ip for i in range(len(native.addresses))] == ["10.0.0.1"]
    # And we can validate back from the native object.
    m2 = PeerModel.from_cpp(native)
    assert m2.peer_id == "P"


