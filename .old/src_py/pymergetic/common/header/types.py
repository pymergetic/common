"""Type definitions for header/impl introspection."""

from __future__ import annotations

from importlib import import_module
from typing import Any, Optional, Type

from pydantic import BaseModel, Field, PrivateAttr

from pymergetic.common.header.exceptions import ClassReferenceError, HeaderMetaError
from pymergetic.common.header.resolve import resolve_impl


class ClassInfo(BaseModel):
    """Metadata about a class (name, qualname, module, and serializable reference)."""

    name: str = Field(description="Class name")
    qualname: str = Field(description="Qualified class name")
    module: str = Field(description="Module name")
    ref: Optional["ClassReference"] = Field(
        default=None, description="Serializable reference to the class"
    )


class ClassReference(BaseModel):
    """Serializable reference to a class."""

    module: str = Field(description="Module name")
    name: str = Field(description="Class name")

    _cls: Optional[type] = PrivateAttr(default=None)

    model_config = {"arbitrary_types_allowed": True}

    def resolve(self) -> type:
        if self._cls is not None:
            return self._cls

        mod = import_module(self.module)
        cls = getattr(mod, self.name)
        if not isinstance(cls, type):
            raise ClassReferenceError(f"{self.module}.{self.name} is not a class")

        self._cls = cls
        return cls

    @classmethod
    def from_class(cls, class_obj: type) -> "ClassReference":
        ref = cls(module=class_obj.__module__, name=class_obj.__name__)
        ref._cls = class_obj
        return ref

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ClassReference):
            return self.module == other.module and self.name == other.name
        return False

    def __hash__(self) -> int:
        return hash((self.module, self.name))


class ImplInfo(BaseModel):
    resolved: bool = Field(description="Whether the implementation has been resolved")
    name: Optional[str] = Field(default=None, description="Implementation class name")
    qualname: Optional[str] = Field(default=None, description="Qualified implementation class name")
    module: Optional[str] = Field(default=None, description="Implementation module name")
    ref: Optional["ClassReference"] = Field(
        default=None, description="Serializable reference to the implementation class"
    )


class HeaderMeta(BaseModel):
    """Metadata about a header/impl relationship."""

    header: ClassInfo = Field(description="Header class information")
    impl: ImplInfo = Field(description="Implementation information")

    @property
    def header_cls(self) -> Optional[type]:
        if self.header.ref is None:
            return None
        return self.header.ref.resolve()

    @property
    def impl_cls(self) -> Optional[type]:
        if self.impl.ref is None:
            return None
        return self.impl.ref.resolve()

    def make_new_method(self) -> Any:
        header_cls = self.header_cls
        if header_cls is None:
            raise HeaderMetaError("HeaderMeta.header.ref must be set to create __new__ method")

        @staticmethod
        def __new__(cls: Type[Any], *args: Any, **kwargs: Any) -> Any:
            if cls is not header_cls:
                return object.__new__(cls)

            meta = getattr(cls, "__header_meta__", None)
            if meta is not None and isinstance(meta, HeaderMeta):
                impl_cls = meta.impl_cls
                if impl_cls is None:
                    impl_cls = resolve_impl(cls)
                    meta.impl.ref = ClassReference.from_class(impl_cls)
            else:
                impl_cls = resolve_impl(cls)

            return object.__new__(impl_cls)

        return __new__

    @classmethod
    def from_class(cls, header_cls: type) -> "HeaderMeta":
        header_info = ClassInfo(
            name=header_cls.__name__,
            qualname=header_cls.__qualname__,
            module=header_cls.__module__,
            ref=ClassReference.from_class(header_cls),
        )
        impl_info = ImplInfo(resolved=False)
        return cls(header=header_info, impl=impl_info)


__all__ = ["ClassInfo", "ClassReference", "ImplInfo", "HeaderMeta"]


