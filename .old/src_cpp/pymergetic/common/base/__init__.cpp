#include <pymergetic/easybind/prelude.hpp>

namespace pymergetic::common::bindings {

void bind_base(::nanobind::module_& /*m*/) {}

EASYBIND_REGISTER_PACKAGE("pymergetic.common", [](::nanobind::module_& m) { bind_base(m); });

}  // namespace pymergetic::common::bindings
