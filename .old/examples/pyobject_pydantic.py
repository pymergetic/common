from __future__ import annotations

from pydantic import BaseModel

from pymergetic.common import PyObject


def main() -> None:
    # This sample uses the common package's test extension to demonstrate the API.
    from pymergetic.common import __cpp_test__ as ext  # type: ignore

    svc = ext.make_network_service()
    svc.connect("http://example")

    class StatusResponse(BaseModel):
        service: PyObject[object]

    payload = StatusResponse(service=PyObject(svc))

    print("python repr:", payload.service)
    print("python dict snapshot:", payload.service.to_dict())
    print("json (via pydantic -> calls C++ to_dict):")
    print(payload.model_dump_json())


if __name__ == "__main__":
    main()


