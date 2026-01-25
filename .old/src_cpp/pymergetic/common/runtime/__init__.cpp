#include <pymergetic/easybind/prelude.hpp>

namespace pymergetic::common::bindings {

void bind_runtime(::nanobind::module_& /*m*/) {}

EASYBIND_REGISTER_PACKAGE("pymergetic.common", [](::nanobind::module_& m) { bind_runtime(m); });

}  // namespace pymergetic::common::bindings
