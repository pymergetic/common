from __future__ import annotations

import importlib

try:
    _ni = importlib.import_module("pymergetic.common._internal")  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "pymergetic-common net native module is required. "
        "Build/install a wheel with the compiled extension and ensure "
        "`pymergetic.common._internal` is importable."
    ) from e


Frame = _ni.Frame
from pymergetic.common.net.peer_info import AuthKind, PeerInfo, TransportKind
UdsDialer = _ni.UdsDialer
UdsStream = _ni.UdsStream
PmdgChannel = _ni.PmdgChannel

CodecError = _ni.CodecError
EndOfStreamError = _ni.EndOfStreamError
MagicMismatchError = _ni.MagicMismatchError

__all__ = [
    "Frame",
    "PeerInfo",
    "TransportKind",
    "AuthKind",
    "UdsDialer",
    "UdsStream",
    "PmdgChannel",
    "CodecError",
    "EndOfStreamError",
    "MagicMismatchError",
]


