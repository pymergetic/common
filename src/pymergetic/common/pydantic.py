from __future__ import annotations

import os
from importlib import import_module
from typing import Any, TypeVar, Callable, Type, cast, Iterable

from pydantic import BaseModel, ConfigDict, PrivateAttr


def _cppmodel_check_fields(model_cls: type["CppModel"], cpp_type: object) -> None:
    missing = [name for name in model_cls.model_fields.keys() if not hasattr(cpp_type, name)]
    if missing:
        raise TypeError(
            f"{model_cls.__name__} fields not found on {cpp_type!r}: {missing}. "
            "Ensure nanobind exposes them via def_ro/def_rw with matching names."
        )


_TModel = TypeVar("_TModel", bound=Type[BaseModel])


def _resolve_cpp_type(cpp_path: str) -> object:
    mod_name, _, attr = cpp_path.rpartition(".")
    if not mod_name:
        raise TypeError(f"cpp type must be a dotted path, got: {cpp_path!r}")
    mod = import_module(mod_name)
    return getattr(mod, attr)


def _validate_cpp_type_fields(model_cls: type[BaseModel], cpp_path: str) -> None:
    native = _resolve_cpp_type(cpp_path)
    model_fields = getattr(model_cls, "model_fields", None)
    if model_fields is None:
        raise TypeError(f"{model_cls.__name__} does not look like a Pydantic v2 model (missing model_fields)")
    missing = [name for name in model_fields.keys() if not hasattr(native, name)]
    if missing:
        raise TypeError(
            f"{model_cls.__name__} fields not found on {cpp_path}: {missing}. "
            "Ensure nanobind exposes them via def_ro/def_rw with matching names."
        )


def cpp_model(
    cpp_type: str | type,
    *,
    validate: bool | str = "lazy",
    validate_env: str = "PYMERGETIC_CPPMODEL_VALIDATE",
) -> Callable[[_TModel], _TModel]:
    """Decorator for `CppModel` classes declaring their backing native type.

    Example:

    ```python
    @cpp_model("pymergetic.axon._internal.PeerInfo")
    class PeerInfoModel(CppModel):
        peer_id: str
        addresses: list[str]
    ```

    Validation behavior is controlled by `validate`:

    - `validate="lazy"` (default): store metadata now; validate on first use (e.g.
      `from_cpp()`, `to_cpp()`, `assert_cpp_compatible()`).
    - `validate="import"` or `validate=True`: validate immediately at decoration time.
    - `validate=False`: never validate the native type at all (pure metadata).

    When validation runs, it checks that every field name exists on the declared
    native type (via `hasattr`).

    A global escape hatch exists for niche environments (docs/type-checking):
    set `PYMERGETIC_CPPMODEL_VALIDATE=0` to force-disable validation everywhere.
    """

    def _decorator(cls: _TModel) -> _TModel:
        # Intentionally works for any Pydantic-based model class (CppModel, SQLModel, etc.).
        # We only rely on `model_fields` existing (Pydantic v2).

        if isinstance(cpp_type, str):
            cpp_path = cpp_type
        else:
            cpp_path = f"{cpp_type.__module__}.{cpp_type.__name__}"

        # Store metadata for introspection/debugging.
        setattr(cls, "__cpp_type__", cpp_path)
        setattr(cls, "__cpp_validate_env__", validate_env)
        setattr(cls, "__cpp_validate_mode__", validate)

        # Import-time validation (explicit).
        validate_now = (validate is True) or (validate == "import")
        if validate_now and os.environ.get(validate_env) != "0":
            try:
                _validate_cpp_type_fields(cast(type[BaseModel], cls), cpp_path)
            except Exception as e:  # pragma: no cover (message is important)
                raise type(e)(
                    f"{e} (while validating cpp_model({cpp_path!r}) at import time; "
                    f"set {validate_env}=0 or use validate='lazy' to defer)."
                ) from e

        return cls

    return _decorator


class CppModel(BaseModel):
    """Base class for Pydantic models backed by nanobind/pybind11 objects.

    Key behavior:
    - `from_attributes=True`: Pydantic reads attributes via getters/properties
      (no intermediate dict/serialization required).

    Subclasses should define normal typed fields; validation will pull values
    from the native object's attributes.
    """

    _cpp_obj: object | None = PrivateAttr(default=None)

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
    )

    @classmethod
    def assert_cpp_compatible(cls, obj: object) -> None:
        """Fail fast if a native object is missing attributes or has invalid types."""

        cls.validate_cpp_binding()
        missing = [name for name in cls.model_fields.keys() if not hasattr(obj, name)]
        if missing:
            raise TypeError(f"{cls.__name__} cannot validate object; missing attrs: {missing}")
        cls.model_validate(obj)

    @classmethod
    def validate_cpp_binding(cls) -> None:
        """Validate the declared native type shape (if this model is decorated)."""

        validate_env = getattr(cls, "__cpp_validate_env__", "PYMERGETIC_CPPMODEL_VALIDATE")
        if os.environ.get(validate_env) == "0":
            return
        validate_mode = getattr(cls, "__cpp_validate_mode__", "lazy")
        if validate_mode is False:
            return
        cpp_path = getattr(cls, "__cpp_type__", None)
        if not cpp_path:
            return
        _validate_cpp_type_fields(cls, cpp_path)

    @classmethod
    def from_cpp(cls, obj: object) -> "CppModel":
        """Validate from a native object and bind the resulting model to it (write-through)."""

        cls.validate_cpp_binding()
        m = cls.model_validate(obj)
        if isinstance(m, CppModel):
            m.bind_cpp(obj)
        return cast(CppModel, m)

    def bind_cpp(self, obj: object) -> None:
        """Bind this model (and nested models) to a native object for write-through updates."""

        self._cpp_obj = obj
        # Bind nested children to matching native attributes when possible.
        for field_name in type(self).model_fields.keys():
            if not hasattr(obj, field_name):
                continue
            native_child = getattr(obj, field_name)
            value = getattr(self, field_name, None)
            self._bind_nested(value, native_child)

    def is_bound_cpp(self) -> bool:
        return self._cpp_obj is not None

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        super().__setattr__(name, value)
        if name.startswith("_"):
            return
        if name not in type(self).model_fields:
            return
        obj = self._cpp_obj
        if obj is None:
            return
        if not hasattr(obj, name):
            return
        current = getattr(self, name)
        native_value = self._to_native_value(current, getattr(obj, name))
        setattr(obj, name, native_value)
        # Rebind nested if we just assigned a new native object.
        self._bind_nested(current, getattr(obj, name))

    def to_cpp(self) -> object:
        """Construct a new native instance and populate it from this model."""

        self.__class__.validate_cpp_binding()
        cpp_path = getattr(self.__class__, "__cpp_type__", None)
        if not cpp_path:
            raise TypeError(f"{self.__class__.__name__} has no declared __cpp_type__; use @cpp_model(...)")
        native_type = _resolve_cpp_type(cpp_path)
        native_obj = native_type()  # type: ignore[operator]
        self.update_cpp(native_obj)
        return native_obj

    def update_cpp(self, obj: object) -> None:
        """Update an existing native object from this model (best-effort in-place)."""

        self.__class__.validate_cpp_binding()
        for field_name in type(self).model_fields.keys():
            if not hasattr(obj, field_name):
                continue
            current_native = getattr(obj, field_name)
            current_value = getattr(self, field_name)
            native_value = self._to_native_value(current_value, current_native)
            setattr(obj, field_name, native_value)
            self._bind_nested(current_value, getattr(obj, field_name))

    def _bind_nested(self, value: Any, native_value: Any) -> None:  # noqa: ANN401
        if isinstance(value, CppModel):
            value.bind_cpp(native_value)
            return
        if isinstance(value, list) and isinstance(native_value, Iterable):
            # Try to bind element-wise (zip) for lists of models.
            native_list = list(native_value)
            for v, nv in zip(value, native_list, strict=False):
                if isinstance(v, CppModel):
                    v.bind_cpp(nv)

    def _to_native_value(self, value: Any, current_native: Any) -> Any:  # noqa: ANN401
        # Prefer reusing already-bound native objects to avoid allocations/copies.
        if isinstance(value, CppModel):
            if value._cpp_obj is not None:
                # Ensure the model is up-to-date on the existing native object.
                value.update_cpp(value._cpp_obj)
                return value._cpp_obj
            # If the native side already has an object, update in place.
            if current_native is not None:
                value.update_cpp(current_native)
                value.bind_cpp(current_native)
                return current_native
            native_child = value.to_cpp()
            value.bind_cpp(native_child)
            return native_child

        if isinstance(value, list):
            # If it's a list of CppModels, attempt in-place update if possible.
            if value and all(isinstance(v, CppModel) for v in value):
                out: list[Any] = []
                for idx, v in enumerate(cast(list[CppModel], value)):
                    existing = None
                    if isinstance(current_native, Iterable):
                        native_list = list(current_native)
                        if idx < len(native_list):
                            existing = native_list[idx]
                    out.append(self._to_native_value(v, existing))
                return out
            return value

        return value


__all__ = ["CppModel", "cpp_model"]


