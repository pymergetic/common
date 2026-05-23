__package_name__ = "pymergetic-common"
__package_module__ = "pymergetic.common"

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version(__package_name__)
except Exception:
    try:
        from setuptools_scm import get_version as _get_version  # type: ignore

        __version__ = _get_version(
            root="../..", relative_to=__file__, local_scheme="no-local-version"
        )
    except Exception:
        __version__ = "0.0.0"

__all__ = ["__package_name__", "__package_module__", "__version__"]
