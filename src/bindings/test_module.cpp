#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

namespace nb = nanobind;

namespace pymergetic::common {

struct NativePeerInfo {
  std::string peer_id;
  std::vector<std::string> addresses;
};

}  // namespace pymergetic::common

NB_MODULE(_test_internal, m) {
  m.doc() = "pymergetic-common test extension (nanobind)";

  m.def("add", [](int a, int b) { return a + b; });

  nb::class_<pymergetic::common::NativePeerInfo>(m, "NativePeerInfo")
      .def(nb::init<>())
      .def_rw("peer_id", &pymergetic::common::NativePeerInfo::peer_id)
      .def_rw("addresses", &pymergetic::common::NativePeerInfo::addresses);
}


