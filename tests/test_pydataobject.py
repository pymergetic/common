from __future__ import annotations

import pytest

from pymergetic.common import PyDataObject


def test_pydataobject_bytes_roundtrip() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    class DataPoint(PyDataObject[object]):
        _native_type = ext.DataPoint

    dp = DataPoint(ext.make_datapoint(7, "hello"))
    blob = dp.to_bytes()
    dp2 = DataPoint.from_bytes(blob)

    assert dp2.to_dict() == {"a": 7, "b": "hello"}


def test_pydataobject_pydantic_json_roundtrip() -> None:
    pydantic = pytest.importorskip("pydantic")
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    class DataPoint(PyDataObject[object]):
        _native_type = ext.DataPoint

    class M(pydantic.BaseModel):
        dp: DataPoint

    m = M(dp=DataPoint(ext.make_datapoint(1, "x")))
    s = m.model_dump_json()
    m2 = M.model_validate_json(s)
    assert m2.dp.to_dict() == {"a": 1, "b": "x"}


