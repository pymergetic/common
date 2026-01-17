#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

namespace nb = nanobind;

namespace pymergetic::common {

struct NativePeerInfo {
  std::string peer_id;
  std::vector<std::string> addresses;
};

struct NativeOptional {
  std::optional<std::string> name;
};

struct NativeAddress {
  std::string ip;
};

struct NativePeerNested {
  std::string peer_id;
  NativeAddress main_address;
  std::vector<NativeAddress> addresses;
};

}  // namespace pymergetic::common

NB_MODULE(_test_internal, m) {
  m.doc() = "pymergetic-common test extension (nanobind)";

  m.def("add", [](int a, int b) { return a + b; });

  nb::class_<pymergetic::common::NativePeerInfo>(m, "NativePeerInfo")
      .def(nb::init<>())
      .def_rw("peer_id", &pymergetic::common::NativePeerInfo::peer_id)
      .def_rw("addresses", &pymergetic::common::NativePeerInfo::addresses);

  nb::class_<pymergetic::common::NativeOptional>(m, "NativeOptional")
      .def(nb::init<>())
      .def_rw("name", &pymergetic::common::NativeOptional::name);

  nb::class_<pymergetic::common::NativeAddress>(m, "NativeAddress")
      .def(nb::init<>())
      .def_rw("ip", &pymergetic::common::NativeAddress::ip);

  nb::class_<pymergetic::common::NativePeerNested>(m, "NativePeerNested")
      .def(nb::init<>())
      .def_rw("peer_id", &pymergetic::common::NativePeerNested::peer_id)
      .def_rw("main_address", &pymergetic::common::NativePeerNested::main_address)
      .def_rw("addresses", &pymergetic::common::NativePeerNested::addresses);

  m.def("make_native_peer_nested", []() {
    pymergetic::common::NativePeerNested p;
    p.peer_id = "QmHash";
    p.main_address.ip = "127.0.0.1";
    p.addresses.push_back(pymergetic::common::NativeAddress{.ip = "10.0.0.1"});
    p.addresses.push_back(pymergetic::common::NativeAddress{.ip = "10.0.0.2"});
    return p;
  });
}


