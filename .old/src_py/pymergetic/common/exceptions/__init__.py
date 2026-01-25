from __future__ import annotations

import importlib


class CodecError(RuntimeError):
    """Base error for codec/serialization failures."""


class EndOfStreamError(CodecError):
    """Thrown when a buffer ends before the requested bytes are available."""


class MagicMismatchError(CodecError):
    """Thrown when the PMDG magic does not match."""


try:
    _ni = importlib.import_module("pymergetic.common.__cpp__")
    CodecError = _ni.CodecError
    EndOfStreamError = _ni.EndOfStreamError
    MagicMismatchError = _ni.MagicMismatchError
except Exception:
    # Pure-Python fallback (no native extension available).
    pass


__all__ = ["CodecError", "EndOfStreamError", "MagicMismatchError"]

