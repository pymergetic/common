from __future__ import annotations

import os
import sys
import types

import pytest
from pydantic import ValidationError

from pymergetic.common.pydantic import CppModel, cpp_model


def test_cppmodel_assert_cpp_compatible_missing_attrs() -> None:
    class M(CppModel):
        a: int
        b: str

    class Native:
        a = 1

    with pytest.raises(TypeError, match="missing attrs"):
        M.assert_cpp_compatible(Native())


def test_cppmodel_assert_cpp_compatible_validates_types() -> None:
    class M(CppModel):
        a: int

    class Native:
        a = "not-an-int"

    with pytest.raises(ValidationError):
        M.assert_cpp_compatible(Native())


def test_cpp_model_decorator_no_env_no_import() -> None:
    # Explicitly disable validation via decorator param; should not import/resolve cpp_type.
    os.environ.pop("PYMERGETIC_CPPMODEL_VALIDATE", None)

    @cpp_model("definitely.not.real.NativeType", validate=False)
    class M(CppModel):
        x: int

    assert getattr(M, "__cpp_type__") == "definitely.not.real.NativeType"


def test_cpp_model_decorator_default_is_fail_fast_on_missing_native() -> None:
    os.environ.pop("PYMERGETIC_CPPMODEL_VALIDATE", None)
    # Default is validate="lazy": should not import at decoration time, but should fail on first use.
    @cpp_model("definitely.not.real.NativeType")
    class M(CppModel):
        x: int

    with pytest.raises(ModuleNotFoundError):
        M.validate_cpp_binding()


def test_cpp_model_decorator_import_mode_is_fail_fast_on_missing_native() -> None:
    os.environ.pop("PYMERGETIC_CPPMODEL_VALIDATE", None)
    with pytest.raises(Exception):
        @cpp_model("definitely.not.real.NativeType", validate="import")
        class M(CppModel):
            x: int


def test_cpp_model_decorator_env_checks_field_names() -> None:
    # Default is validation-on, but set explicitly to keep intent clear.
    os.environ["PYMERGETIC_CPPMODEL_VALIDATE"] = "1"

    mod = types.ModuleType("tmp_native_mod")

    class Native:
        peer_id = "x"
        addresses = ["a"]

    mod.Native = Native
    sys.modules["tmp_native_mod"] = mod

    @cpp_model("tmp_native_mod.Native")
    class Good(CppModel):
        peer_id: str
        addresses: list[str]

    assert getattr(Good, "__cpp_type__") == "tmp_native_mod.Native"
    # Lazy validation: should pass on first use.
    Good.validate_cpp_binding()

    with pytest.raises(TypeError, match="fields not found"):
        @cpp_model("tmp_native_mod.Native")
        class Bad(CppModel):
            missing_field: str

        Bad.validate_cpp_binding()

    os.environ.pop("PYMERGETIC_CPPMODEL_VALIDATE", None)


def test_cppmodel_nested_models_from_attributes() -> None:
    class NativeAddress:
        ip = "127.0.0.1"

    class NativePeer:
        peer_id = "QmHash"
        main_address = NativeAddress()

    class AddressModel(CppModel):
        ip: str

    class PeerModel(CppModel):
        peer_id: str
        main_address: AddressModel

    native = NativePeer()
    model = PeerModel.model_validate(native)

    assert model.peer_id == "QmHash"
    assert model.main_address.ip == "127.0.0.1"


