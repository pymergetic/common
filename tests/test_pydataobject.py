from __future__ import annotations

import pytest

from pymergetic.common import PyDataObject


def test_pydataobject_bytes_roundtrip() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    dp = DataPoint(ext.make_datapoint(7, "hello"))
    blob = dp.to_bytes()
    assert blob[:4] == b"PMDG"
    dp2 = DataPoint.from_bytes(blob)

    assert dp2.to_dict() == {"a": 7, "b": "hello"}


def test_pydataobject_rejects_bad_magic() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    dp = DataPoint(ext.make_datapoint(1, "x"))
    blob = bytearray(dp.to_bytes())
    blob[0:4] = b"NOPE"
    with pytest.raises(ext.MagicMismatchError, match="magic"):
        DataPoint.from_bytes(bytes(blob))


def test_pydataobject_rejects_wrong_type_id() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    dp = DataPoint(ext.make_datapoint(1, "x"))
    blob = bytearray(dp.to_bytes())
    # type_id is little-endian u32 at offset 8
    blob[8] ^= 0xFF
    with pytest.raises(ext.CodecError, match="type_id"):
        DataPoint.from_bytes(bytes(blob))


def test_pydataobject_rejects_truncated_payload() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    dp = DataPoint(ext.make_datapoint(1, "x"))
    blob = dp.to_bytes()
    with pytest.raises(ext.EndOfStreamError):
        DataPoint.from_bytes(blob[:-1])


def test_pydataobject_rejects_length_mismatch() -> None:
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    dp = DataPoint(ext.make_datapoint(1, "x"))
    blob = bytearray(dp.to_bytes())
    # payload_len is little-endian u32 at offset 12; bump it by 1
    blob[12] = (blob[12] + 1) % 256
    with pytest.raises(ext.EndOfStreamError, match="length"):
        DataPoint.from_bytes(bytes(blob))


def test_pydataobject_pydantic_json_roundtrip() -> None:
    pydantic = pytest.importorskip("pydantic")
    ext = pytest.importorskip("pymergetic.common._test_internal", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    class M(pydantic.BaseModel):
        dp: DataPoint

    m = M(dp=DataPoint(ext.make_datapoint(1, "x")))
    s = m.model_dump_json()
    m2 = M.model_validate_json(s)
    assert m2.dp.to_dict() == {"a": 1, "b": "x"}


