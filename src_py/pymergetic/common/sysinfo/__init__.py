from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def _pkg_version(distribution: str) -> str:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return "unknown"


def common_version() -> str:
    return _pkg_version("pymergetic-common")


def easybind_version() -> str:
    return _pkg_version("pymergetic-easybind")


__all__ = ["common_version", "easybind_version"]
