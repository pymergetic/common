from __future__ import annotations

import pytest

from pymergetic.common import PyDataObject, codec


def test_codec_type_id_matches_cpp_payload() -> None:
    ext = pytest.importorskip("pymergetic.common.__cpp_test__", exc_type=ImportError)

    DataPoint = PyDataObject.native(ext.DataPoint)

    dp = DataPoint(ext.make_datapoint(1, "x"))
    blob = dp.to_bytes()

    h = codec.read_header(blob)
    assert h.type_id == codec.type_id("pymergetic.common.DataPoint")


