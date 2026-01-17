from __future__ import annotations

from pydantic import BaseModel

from pymergetic.common import PyDataObject


def main() -> None:
    # This sample uses the common package's test extension to demonstrate the API.
    from pymergetic.common import _test_internal as ext  # type: ignore

    class DataPoint(PyDataObject[object]):
        _native_type = ext.DataPoint

    dp = DataPoint(ext.make_datapoint(7, "hello"))
    blob = dp.to_bytes()
    dp2 = DataPoint.from_bytes(blob)

    print("native snapshot:", dp2.to_dict())
    print("bytes length:", len(blob))

    class Packet(BaseModel):
        dp: DataPoint

    pkt = Packet(dp=dp)
    s = pkt.model_dump_json()
    pkt2 = Packet.model_validate_json(s)

    print("json (base64 bytes payload):")
    print(s)
    print("roundtrip snapshot:", pkt2.dp.to_dict())


if __name__ == "__main__":
    main()


