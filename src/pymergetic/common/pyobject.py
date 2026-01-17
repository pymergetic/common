from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar


T = TypeVar("T")


class PyObject(Generic[T]):
    """Pydantic-free wrapper around a native nanobind object.

    Use this for data-plane/native objects where you want:
    - stable lifetime management (usually shared_ptr on the C++ side)
    - direct method calls on the native object
    - fast serialization via `to_dict()` implemented in C++
    """

    __slots__ = ("_handle",)

    def __init__(self, handle: T) -> None:
        self._handle = handle

    @property
    def cpp(self) -> T:
        return self._handle

    def to_dict(self) -> dict:
        # Expect the C++ object to provide a `to_dict()` method (nanobind bound).
        return dict(self._handle.to_dict())  # type: ignore[attr-defined]

    def __repr__(self) -> str:
        return repr(self._handle)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Callable[[Any], Any],
    ) -> Any:
        """Pydantic v2 integration (passive bridge).

        - Python validation: accept only real PyObject instances
        - JSON input: rejected (native handles can't be constructed from JSON)
        - JSON serialization: uses `to_dict()` (native fast path)
        """

        from pydantic_core import core_schema

        def _reject_json(_v: Any) -> Any:  # noqa: ANN401
            raise ValueError("PyObject cannot be parsed from JSON; it must be provided as a Python object")

        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_plain_validator_function(_reject_json),
            python_schema=core_schema.is_instance_schema(cls),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._pydantic_serialize,
                info_arg=False,
                when_used="json",
            ),
        )

    @staticmethod
    def _pydantic_serialize(obj: "PyObject[Any]") -> Any:  # noqa: ANN401
        return obj.to_dict()


__all__ = ["PyObject"]


