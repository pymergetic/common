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


PeerInfo = _ni.PeerInfo
TransportKind = _ni.TransportKind
AuthKind = _ni.AuthKind

__all__ = ["PeerInfo", "TransportKind", "AuthKind"]


