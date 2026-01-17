from __future__ import annotations

import os
from importlib import import_module
from typing import Any, TypeVar, Callable, Type, cast

from pydantic import BaseModel, ConfigDict


def _cppmodel_check_fields(model_cls: type["CppModel"], cpp_type: object) -> None:
    missing = [name for name in model_cls.model_fields.keys() if not hasattr(cpp_type, name)]
    if missing:
        raise TypeError(
            f"{model_cls.__name__} fields not found on {cpp_type!r}: {missing}. "
            "Ensure nanobind exposes them via def_ro/def_rw with matching names."
        )


_TModel = TypeVar("_TModel", bound=Type[BaseModel])


def cpp_model(
    cpp_type: str | type,
    *,
    validate: bool = True,
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

    By default (`validate=True`), applying this decorator will validate that every
    field name exists on the declared native type (via `hasattr`). This is
    **fail-fast** by design: if the native type cannot be imported/resolved, the
    decorated class definition will raise.

    To disable validation for a specific model (e.g. optional native module),
    pass `validate=False`.

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

        # Default: validate. Opt-out via decorator param or global env kill-switch.
        if validate and os.environ.get(validate_env) != "0":
            mod_name, _, attr = cpp_path.rpartition(".")
            if not mod_name:
                raise TypeError(f"{cls.__name__} cpp type must be a dotted path, got: {cpp_path!r}")
            try:
                mod = import_module(mod_name)
            except Exception as e:  # pragma: no cover (message is important)
                raise ImportError(
                    f"{cls.__name__} could not import native module {mod_name!r} while validating "
                    f"cpp_model({cpp_path!r}). If this model requires a native extension, ensure it is "
                    f"installed/built; otherwise set {validate_env}=0 to disable this validation."
                ) from e
            try:
                native = getattr(mod, attr)
            except Exception as e:
                raise ImportError(
                    f"{cls.__name__} could not resolve native type {cpp_path!r} while validating "
                    f"cpp_model(...). Ensure the module exports {attr!r}; otherwise set {validate_env}=0."
                ) from e

            # Pydantic v2 models have `model_fields`; SQLModel too.
            model_fields = getattr(cls, "model_fields", None)
            if model_fields is None:
                raise TypeError(f"{cls.__name__} does not look like a Pydantic v2 model (missing model_fields)")
            missing = [name for name in model_fields.keys() if not hasattr(native, name)]
            if missing:
                raise TypeError(
                    f"{cls.__name__} fields not found on {cpp_path}: {missing}. "
                    "Ensure nanobind exposes them via def_ro/def_rw with matching names."
                )

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

    model_config = ConfigDict(
        from_attributes=True,
    )

    @classmethod
    def assert_cpp_compatible(cls, obj: object) -> None:
        """Fail fast if a native object is missing attributes or has invalid types."""

        missing = [name for name in cls.model_fields.keys() if not hasattr(obj, name)]
        if missing:
            raise TypeError(f"{cls.__name__} cannot validate object; missing attrs: {missing}")
        cls.model_validate(obj)


__all__ = ["CppModel", "cpp_model"]


