from __future__ import annotations

import os
from importlib import import_module
from typing import Any, TypeVar, Callable, Type, cast, Iterable, Iterator

from pydantic import BaseModel, ConfigDict, PrivateAttr


class _BoundList(list):
    """A list that notifies its owning CppModel on structural mutations.

    This exists to avoid the silent desync where `model.list_field.append(...)`
    mutates only Python state. When bound, we re-sync the corresponding native
    container after each structural mutation.

    Notes:
    - Element *mutations* like `model.list_field[i].x = ...` are handled by the
      child model's own write-through binding (no container rebuild).
    - Structural mutations are currently implemented as a re-sync of the entire
      container (O(N)). For true O(1) structural edits, we'd need a dedicated
      nanobind-exposed vector wrapper (push_back/erase/etc.) instead of relying
      on automatic STL conversions.
    """

    def __init__(self, owner: "CppModel", field_name: str, iterable: Iterable[Any] = ()) -> None:
        super().__init__(iterable)
        self._owner = owner
        self._field_name = field_name

    def _sync(self) -> None:
        self._owner._on_bound_list_mutation(self._field_name)

    def _try_native_op(self, op: str, *args: Any) -> bool:  # noqa: ANN401
        """Try a granular native container operation; return True if performed."""

        return self._owner._on_bound_list_op(self._field_name, op, *args)

    # Structural mutation hooks
    def append(self, item: Any) -> None:  # noqa: ANN401
        super().append(item)
        if not self._try_native_op("append", item):
            self._sync()

    def extend(self, iterable: Iterable[Any]) -> None:  # noqa: ANN401
        items = list(iterable)
        super().extend(items)
        if not self._try_native_op("extend", items):
            self._sync()

    def insert(self, index: int, item: Any) -> None:  # noqa: ANN401
        super().insert(index, item)
        # Native views rarely support insert efficiently; fall back.
        if not self._try_native_op("insert", index, item):
            self._sync()

    def pop(self, index: int = -1) -> Any:  # noqa: ANN401
        v = super().pop(index)
        if not self._try_native_op("pop", index):
            self._sync()
        return v

    def remove(self, item: Any) -> None:  # noqa: ANN401
        super().remove(item)
        if not self._try_native_op("remove", item):
            self._sync()

    def clear(self) -> None:
        super().clear()
        if not self._try_native_op("clear"):
            self._sync()

    def __delitem__(self, key: int | slice) -> None:
        super().__delitem__(key)
        if not self._try_native_op("delitem", key):
            self._sync()

    def __setitem__(self, key: int | slice, value: Any) -> None:  # noqa: ANN401
        super().__setitem__(key, value)
        if not self._try_native_op("setitem", key, value):
            self._sync()

    def sort(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        super().sort(*args, **kwargs)
        self._sync()

    def reverse(self) -> None:
        super().reverse()
        self._sync()

    # Preserve type on slicing
    def __getitem__(self, item: int | slice) -> Any:  # noqa: ANN401
        v = super().__getitem__(item)
        if isinstance(item, slice):
            return _BoundList(self._owner, self._field_name, v)
        return v


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

    Write-through binding:
    - Use `Model.from_cpp(native)` to bind a validated model to a native object.
    - Assignments like `model.x = 1` write through to `native.x`.
    - For list fields, the model wraps them with an observable list so operations
      like `append()` and `del` also re-sync the native container.

    Important binding requirement:
    - Nested objects MUST be exposed by nanobind using reference semantics
      (e.g., `def_rw` or `def_prop_rw(..., rv_policy::reference_internal)`),
      otherwise binding can attach to temporary copies.

    Important container requirement (for bidirectional containers):
    - If a C++ container is exposed via automatic STL conversion (e.g. a
      `std::vector<T>` property that appears as a Python `list`), Python will
      typically receive a **copy**. Structural mutations on that list will not
      update C++.
    - For true bidirectional container sync and O(1) structural ops, expose a
      dedicated nanobind "view/proxy" type with methods like `append`, `erase`,
      `clear`, and `__getitem__` returning `reference_internal`.
    """

    _cpp_obj: object | None = PrivateAttr(default=None)
    _cpp_sync_suspended: bool = PrivateAttr(default=False)

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
        # Also wrap list fields so structural mutations re-sync the native container.
        self._cpp_sync_suspended = True
        try:
            for field_name in type(self).model_fields.keys():
                if not hasattr(obj, field_name):
                    continue
                native_child = getattr(obj, field_name)
                value = getattr(self, field_name, None)
                if isinstance(value, list) and not isinstance(value, _BoundList):
                    # Use raw setattr to avoid Pydantic coercing list subclasses back to `list`.
                    object.__setattr__(self, field_name, _BoundList(self, field_name, value))
                    value = getattr(self, field_name)
                self._bind_nested(value, native_child)
        finally:
            self._cpp_sync_suspended = False

    def is_bound_cpp(self) -> bool:
        return self._cpp_obj is not None

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        super().__setattr__(name, value)
        if name.startswith("_"):
            return
        if name not in type(self).model_fields:
            return
        if self._cpp_sync_suspended:
            return
        obj = self._cpp_obj
        if obj is None:
            return
        if not hasattr(obj, name):
            return
        current = getattr(self, name)
        if isinstance(current, list) and not isinstance(current, _BoundList):
            # Ensure list fields are observable after assignment.
            self._cpp_sync_suspended = True
            try:
                object.__setattr__(self, name, _BoundList(self, name, current))
                current = getattr(self, name)
            finally:
                self._cpp_sync_suspended = False
        native_container = getattr(obj, name)
        # Prefer in-place container update for list fields exposed as live views.
        if isinstance(current, list) and hasattr(native_container, "clear") and hasattr(native_container, "append"):
            native_container.clear()
            for item in current:
                native_container.append(self._to_native_value(item, None))
            self._bind_nested(current, native_container)
            return

        native_value = self._to_native_value(current, native_container)
        try:
            setattr(obj, name, native_value)
        except AttributeError:
            # If there's no setter but we have a live container, try in-place.
            if isinstance(current, list) and hasattr(native_container, "clear") and hasattr(native_container, "append"):
                native_container.clear()
                for item in current:
                    native_container.append(self._to_native_value(item, None))
                self._bind_nested(current, native_container)
                return
            raise
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
            current_value = getattr(self, field_name)
            native_container = getattr(obj, field_name)
            if isinstance(current_value, list) and hasattr(native_container, "clear") and hasattr(native_container, "append"):
                native_container.clear()
                for item in current_value:
                    native_container.append(self._to_native_value(item, None))
                self._bind_nested(current_value, native_container)
                continue

            native_value = self._to_native_value(current_value, native_container)
            try:
                setattr(obj, field_name, native_value)
            except AttributeError:
                if isinstance(current_value, list) and hasattr(native_container, "clear") and hasattr(native_container, "append"):
                    native_container.clear()
                    for item in current_value:
                        native_container.append(self._to_native_value(item, None))
                    self._bind_nested(current_value, native_container)
                    continue
                raise
            self._bind_nested(current_value, getattr(obj, field_name))

    def _on_bound_list_mutation(self, field_name: str) -> None:
        """Called by _BoundList after a structural mutation."""

        if self._cpp_sync_suspended:
            return
        obj = self._cpp_obj
        if obj is None or not hasattr(obj, field_name):
            return
        current = getattr(self, field_name, None)
        native_container = getattr(obj, field_name)

        # Prefer in-place container mutation when the binding exposes a live container
        # (e.g., a nanobind "view" with clear()/append()).
        if hasattr(native_container, "clear") and hasattr(native_container, "append"):
            native_container.clear()
            if isinstance(current, list):
                for item in current:
                    native_item = self._to_native_value(item, None)
                    native_container.append(native_item)
            # Rebind from the live container (no setattr needed).
            self._bind_nested(current, native_container)
            return

        # Fallback: best-effort attribute assignment (works only if setter is live).
        native_value = self._to_native_value(current, native_container)
        setattr(obj, field_name, native_value)
        self._bind_nested(current, getattr(obj, field_name))

    def _on_bound_list_op(self, field_name: str, op: str, *args: Any) -> bool:  # noqa: ANN401
        """Attempt an O(1)/granular native list operation.

        Returns True if the operation was applied to the native container.
        """

        if self._cpp_sync_suspended:
            return False
        obj = self._cpp_obj
        if obj is None or not hasattr(obj, field_name):
            return False

        native_container = getattr(obj, field_name)
        try:
            if op == "append" and hasattr(native_container, "append"):
                (item,) = args
                native_container.append(self._to_native_value(item, None))
                return True

            if op == "extend" and hasattr(native_container, "append"):
                (items,) = args
                for item in items:
                    native_container.append(self._to_native_value(item, None))
                return True

            if op == "clear" and hasattr(native_container, "clear"):
                native_container.clear()
                return True

            if op == "pop" and hasattr(native_container, "erase") and hasattr(native_container, "__len__"):
                (index,) = args
                n = len(native_container)
                # Mirror Python negative indexing.
                i = index if index >= 0 else n + index
                if i < 0 or i >= n:
                    return False
                native_container.erase(i)
                return True

            if op == "delitem" and hasattr(native_container, "erase") and hasattr(native_container, "__len__"):
                (key,) = args
                if isinstance(key, slice):
                    return False
                n = len(native_container)
                i = key if key >= 0 else n + key
                if i < 0 or i >= n:
                    return False
                native_container.erase(i)
                return True

            if op == "setitem" and hasattr(native_container, "__setitem__") and hasattr(native_container, "__len__"):
                key, value = args
                if isinstance(key, slice):
                    return False
                n = len(native_container)
                i = key if key >= 0 else n + key
                if i < 0 or i >= n:
                    return False
                native_container[i] = self._to_native_value(value, None)
                return True

            # Not supported efficiently.
            return False
        except Exception:
            # Any native failure should fall back to a full re-sync path.
            return False

    def _bind_nested(self, value: Any, native_value: Any) -> None:  # noqa: ANN401
        if isinstance(value, CppModel):
            value.bind_cpp(native_value)
            return
        if isinstance(value, list):
            # Bind element-wise. Avoid materializing lists if the native value is a
            # live indexed container (preferred).
            if hasattr(native_value, "__len__") and hasattr(native_value, "__getitem__"):
                n = len(native_value)  # type: ignore[arg-type]
                for i, v in enumerate(value):
                    if i >= n:
                        break
                    if isinstance(v, CppModel):
                        v.bind_cpp(native_value[i])  # type: ignore[index]
                return
            if isinstance(native_value, Iterable):
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


