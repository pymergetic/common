from __future__ import annotations

import importlib

try:
    _native = importlib.import_module("pymergetic.common.sysinfo.__cpp__")  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "pymergetic-common sysinfo native module is required. "
        "Build/install a wheel with the compiled extension and ensure "
        "`pymergetic.common.sysinfo.__cpp__` is importable."
    ) from e

common_version = _native.common_version
easybind_version = _native.easybind_version

__all__ = ["common_version", "easybind_version"]
