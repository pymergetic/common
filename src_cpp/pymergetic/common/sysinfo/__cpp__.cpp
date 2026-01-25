#include <pymergetic/easybind/prelude.hpp>

#include <string>

namespace nb = nanobind;

namespace pymergetic::common::sysinfo {

static std::string module_version(const char* module_name) {
  try {
    nb::module_ mod = nb::module_::import_(module_name);
    nb::str version = nb::str(mod.attr("__version__"));
    return std::string(version.c_str());
  } catch (const std::exception&) {
    return "unknown";
  }
}

std::string common_version() {
  return module_version("pymergetic.common");
}

std::string easybind_version() {
  return module_version("pymergetic.easybind");
}

}  // namespace pymergetic::common::sysinfo

EASYBIND_MODULE("pymergetic.common.sysinfo");

namespace pymergetic::common::sysinfo {

EASYBIND_REGISTER_FUNC(common_version);
EASYBIND_REGISTER_FUNC(easybind_version);

}  // namespace pymergetic::common::sysinfo
