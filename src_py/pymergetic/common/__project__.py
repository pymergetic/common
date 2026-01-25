from pymergetic.easybind.version import get_version as _get_version, get_version_cpp as _get_version_cpp


__package_name__ = "pymergetic-common"
__package_module__ = "pymergetic.common"

__version__ = _get_version(__package_name__, root="../../..", relative_to=__file__)
__version_cpp__ = _get_version_cpp(__package_module__)


__all__ = ["__package_name__", "__package_module__", "__version__", "__version_cpp__"]
