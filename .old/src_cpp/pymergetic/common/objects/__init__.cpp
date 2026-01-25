#include <pymergetic/easybind/prelude.hpp>

namespace pymergetic::common::bindings {

void bind_objects(::nanobind::module_& /*m*/) {}

EASYBIND_REGISTER_PACKAGE("pymergetic.common", [](::nanobind::module_& m) { bind_objects(m); });

}  // namespace pymergetic::common::bindings
