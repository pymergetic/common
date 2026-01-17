from __future__ import annotations

"""Implementation resolver for header classes."""

from importlib import import_module
import inspect
from typing import Any, Type

from pymergetic.common.header.exceptions import (
    HeaderPackageError,
    ImplModuleNotFoundError,
    MultipleImplsFoundError,
    NoImplFoundError,
)


def resolve_impl(header_cls: Type[Any]) -> Type[Any]:
    """Resolve the implementation class for a header.

    Locates the `__impl__` module in the header's package and finds the single
    subclass of the header class that is defined in that module (not imported).
    """

    header_module = import_module(header_cls.__module__)
    
    # Get the impl module from the header module's package
    package = header_module.__package__
    if package is None:
        raise HeaderPackageError(f"Header {header_cls.__qualname__} module has no package")

    # Access __impl__ from the package
    package_module = import_module(package)
    impl_module = getattr(package_module, "__impl__", None)
    impl_module_name = f"{package}.__impl__"
    if impl_module is None:
        # Try importing it explicitly
        try:
            impl_module = import_module(impl_module_name)
        except ImportError as e:
            raise ImplModuleNotFoundError(
                f"Could not find __impl__ module for header {header_cls.__qualname__}: {e}"
            ) from e
    else:
        impl_module_name = impl_module.__name__

    subclasses: list[Type[Any]] = []
    for _name, obj in inspect.getmembers(impl_module, inspect.isclass):
        if (  # CRITICAL: only consider classes actually defined in impl module (not imported)
            obj is not header_cls
            and issubclass(obj, header_cls)
            and getattr(obj, "__module__", None) == impl_module_name
        ):
            subclasses.append(obj)

    if not subclasses:
        raise NoImplFoundError(
            f"No implementation subclass found in impl module for header {header_cls.__qualname__}"
        )
    if len(subclasses) > 1:
        raise MultipleImplsFoundError(
            f"Multiple implementation subclasses found for header {header_cls.__qualname__}: "
            f"{[cls.__name__ for cls in subclasses]}"
        )
    return subclasses[0]


