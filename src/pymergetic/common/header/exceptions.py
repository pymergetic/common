"""Custom exceptions for header resolution."""


class HeaderResolutionError(Exception):
    """Base exception for header resolution errors."""


class HeaderPackageError(HeaderResolutionError):
    """Raised when a header class's module has no package."""


class ImplModuleNotFoundError(HeaderResolutionError):
    """Raised when the __impl__ module cannot be found."""


class NoImplFoundError(HeaderResolutionError):
    """Raised when no implementation subclass is found."""


class MultipleImplsFoundError(HeaderResolutionError):
    """Raised when multiple implementation subclasses are found."""


class ClassReferenceError(HeaderResolutionError):
    """Raised when a class reference cannot be resolved."""


class HeaderMetaError(HeaderResolutionError):
    """Raised when HeaderMeta is in an invalid state."""


__all__ = [
    "HeaderResolutionError",
    "HeaderPackageError",
    "ImplModuleNotFoundError",
    "NoImplFoundError",
    "MultipleImplsFoundError",
    "ClassReferenceError",
    "HeaderMetaError",
]


