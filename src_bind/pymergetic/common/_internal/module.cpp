#include <nanobind/nanobind.h>
namespace nb = nanobind;

namespace pymergetic::common::bindings {
void bind_net(::nanobind::module_& m);
}  // namespace pymergetic::common::bindings

NB_MODULE(_internal, m) {
  m.doc() = "pymergetic-common consolidated native bindings";
  pymergetic::common::bindings::bind_net(m);
}


