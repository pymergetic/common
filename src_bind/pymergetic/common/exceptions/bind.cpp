#include <nanobind/nanobind.h>

#include <pymergetic/common/exceptions/__init__.hpp>

namespace pymergetic::common::bindings {

namespace nb = ::nanobind;

void bind_exceptions(::nanobind::module_& m) {
  nb::exception<pymergetic::common::CodecError>(m, "CodecError");
  nb::exception<pymergetic::common::EndOfStreamError>(m, "EndOfStreamError");
  nb::exception<pymergetic::common::MagicMismatchError>(m, "MagicMismatchError");
}

}  // namespace pymergetic::common::bindings


