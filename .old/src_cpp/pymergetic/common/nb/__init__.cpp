#include <pymergetic/easybind/prelude.hpp>

namespace pymergetic::common::bindings {

void bind_nb(::nanobind::module_& /*m*/) {}

EASYBIND_REGISTER_PACKAGE("pymergetic.common", [](::nanobind::module_& m) { bind_nb(m); });

}  // namespace pymergetic::common::bindings
