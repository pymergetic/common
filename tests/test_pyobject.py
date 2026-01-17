from __future__ import annotations

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


