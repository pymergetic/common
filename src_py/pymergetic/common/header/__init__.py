"""Header resolution toolkit.

Canonical implementation lives in `pymergetic-common` and is reused by all
packages.
"""

from pymergetic.common.header.decorators import header
from pymergetic.common.header.resolve import resolve_impl
from pymergetic.common.header.types import ClassInfo, ClassReference, HeaderMeta, ImplInfo

__all__ = [
    "header",
    "resolve_impl",
    "ClassInfo",
    "ClassReference",
    "HeaderMeta",
    "ImplInfo",
]


