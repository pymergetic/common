from __future__ import annotations

"""Decorators for wiring headers to their implementations explicitly."""

from typing import Any, Type

from pymergetic.common.header.types import HeaderMeta

def header(header_cls: Type[Any]) -> Type[Any]:
    """Decorator for header classes to mark them as headers."""

    meta = HeaderMeta.from_class(header_cls)
    header_cls.__new__ = meta.make_new_method()
    header_cls.__header_meta__ = meta
    return header_cls


