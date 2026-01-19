from __future__ import annotations

import base64
import types
import weakref
from typing import Any, Callable, ClassVar, Generic, TypeVar


T = TypeVar("T")

_PYDATAOBJECT_TYPE_CACHE: "weakref.WeakKeyDictionary[Any, type[PyDataObject[Any]]]" = weakref.WeakKeyDictionary()


class PyDataObject(Generic[T]):
    """Pydantic-friendly wrapper for *pure data* native objects.

    Unlike `PyObject`, this represents idempotently recoverable data.

    Contract for the native type (nanobind-exposed):
    - `serialize() -> bytes`
    - `@staticmethod deserialize(data: bytes) -> NativeType`
    - optionally `to_dict() -> dict` and `__repr__`
    """

    __slots__ = ("_handle",)

    # Concrete subclasses MUST set this.
    _native_type: ClassVar[Any]

    @classmethod
    def native(cls, native_type: Any, *, name: str | None = None) -> type["PyDataObject[Any]"]:
        """Create (and cache) a concrete PyDataObject wrapper for a native type.

        This avoids boilerplate like:

            class X(PyDataObject[object]):
                _native_type = ext.X

        Usage:
            X = PyDataObject.native(ext.X)
            x = X(ext.make_x(...))
        """

        cached = _PYDATAOBJECT_TYPE_CACHE.get(native_type)
        if cached is not None:
            return cached

        cls_name = name or getattr(native_type, "__name__", "NativeDataObject")
        # IMPORTANT: do not use `PyDataObject[Any]` here (it's a typing alias, not a real class).
        wrapper = types.new_class(
            cls_name,
            (PyDataObject,),
            exec_body=lambda ns: ns.update(
                {
                    "_native_type": native_type,
                    "__module__": cls.__module__,
                }
            ),
        )
        _PYDATAOBJECT_TYPE_CACHE[native_type] = wrapper
        return wrapper

    def __init__(self, handle: T) -> None:
        self._handle = handle

    @property
    def cpp(self) -> T:
        return self._handle

    def to_bytes(self) -> bytes:
        return bytes(self._handle.serialize())  # type: ignore[attr-defined]

    @classmethod
    def from_bytes(cls, data: bytes) -> "PyDataObject[T]":
        native_type = getattr(cls, "_native_type", None)
        if native_type is None:
            raise TypeError(f"{cls.__name__} must define _native_type")
        handle = native_type.deserialize(data)  # type: ignore[attr-defined]
        return cls(handle)

    def to_dict(self) -> dict:
        # Optional, for debugging/inspection.
        if hasattr(self._handle, "to_dict"):
            return dict(self._handle.to_dict())  # type: ignore[attr-defined]
        return {}

    def __repr__(self) -> str:
        return repr(self._handle)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: Callable[[Any], Any],
    ) -> Any:
        """Pydantic v2 integration (round-trip safe).

        JSON representation is a base64 string of the serialized bytes, so the
        object is idempotently recoverable regardless of global Pydantic settings.

        NOTE: For large payloads, base64-in-JSON is inefficient. Prefer storing
        or transmitting the raw bytes out-of-band (files, blobs, streaming APIs)
        and keep JSON for metadata/small payloads.
        """

        from pydantic_core import core_schema

        def _from_native(v: Any) -> "PyDataObject[T]":  # noqa: ANN401
            native_type = getattr(cls, "_native_type", None)
            if native_type is None:
                raise TypeError(f"{cls.__name__} must define _native_type")
            if isinstance(v, cls):
                return v
            if isinstance(v, native_type):
                return cls(v)
            raise TypeError(f"Expected {cls.__name__} or {native_type}, got {type(v)}")

        def _from_bytes(v: bytes) -> "PyDataObject[T]":
            return cls.from_bytes(v)

        def _from_b64(s: str) -> "PyDataObject[T]":
            try:
                raw = base64.b64decode(s.encode("ascii"), validate=True)
            except Exception as e:
                raise ValueError("Invalid base64 payload for PyDataObject") from e
            return cls.from_bytes(raw)

        return core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_after_validator_function(_from_b64, core_schema.str_schema()),
            python_schema=core_schema.no_info_plain_validator_function(_from_native),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._pydantic_serialize,
                info_arg=False,
                when_used="json",
            ),
        )

    @staticmethod
    def _pydantic_serialize(obj: "PyDataObject[Any]") -> str:
        return base64.b64encode(obj.to_bytes()).decode("ascii")


__all__ = ["PyDataObject"]


