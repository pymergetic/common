from __future__ import annotations

import gc
import pytest

from pymergetic.common import PyObject


def test_pyobject_cppbase_to_dict_and_repr() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    svc = ext.make_network_service()
    obj = PyObject(svc)

    assert repr(obj) == "<NetworkService>"
    assert obj.to_dict()["status"] == "disconnected"

    obj.cpp.connect("http://example")
    assert obj.to_dict()["status"] == "connected:http://example"


def test_cpp_shared_ptr_lifetime_survives_python_gc() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    svc = ext.make_network_service()
    ext.cpp_hold_network_service(svc)

    # Drop Python references and force collection.
    del svc
    gc.collect()

    svc2 = ext.cpp_get_held_network_service()
    assert svc2 is not None
    assert svc2.to_dict()["status"] == "disconnected"
    ext.cpp_clear_held_network_service()


