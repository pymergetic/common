#include <pymergetic/easybind/prelude.hpp>

#include <pymergetic/common/exceptions/__init__.hpp>

namespace pymergetic::common::bindings {

namespace nb = ::nanobind;

void bind_exceptions(::nanobind::module_& m) {
  nb::exception<pymergetic::common::CodecError>(m, "CodecError");
  nb::exception<pymergetic::common::EndOfStreamError>(m, "EndOfStreamError");
  nb::exception<pymergetic::common::MagicMismatchError>(m, "MagicMismatchError");
}

EASYBIND_REGISTER_PACKAGE("pymergetic.common", [](::nanobind::module_& m) { bind_exceptions(m); });

}  // namespace pymergetic::common::bindings
