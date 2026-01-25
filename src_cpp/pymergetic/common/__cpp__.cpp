#include <pymergetic/easybind/prelude.hpp>

EASYBIND_MODULE("pymergetic.common");

namespace pymergetic::common {

EASYBIND_REGISTER_PACKAGE_ATTR("__version__", EASYBIND_BUILD_VERSION);

}  // namespace pymergetic::common
