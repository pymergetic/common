from __future__ import annotations

from typing import Generic, TypeVar


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


__all__ = ["PyObject"]


