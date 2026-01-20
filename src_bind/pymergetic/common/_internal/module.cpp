#include <nanobind/nanobind.h>
namespace nb = nanobind;

namespace pymergetic::common::bindings {
void bind_base(::nanobind::module_& m);
void bind_codec(::nanobind::module_& m);
void bind_exceptions(::nanobind::module_& m);
void bind_header(::nanobind::module_& m);
void bind_nb(::nanobind::module_& m);
void bind_net(::nanobind::module_& m);
void bind_objects(::nanobind::module_& m);
void bind_runtime(::nanobind::module_& m);
void bind_session(::nanobind::module_& m);
}  // namespace pymergetic::common::bindings

NB_MODULE(_internal, m) {
  m.doc() = "pymergetic-common consolidated native bindings";
  pymergetic::common::bindings::bind_base(m);
  pymergetic::common::bindings::bind_codec(m);
  pymergetic::common::bindings::bind_exceptions(m);
  pymergetic::common::bindings::bind_header(m);
  pymergetic::common::bindings::bind_nb(m);
  pymergetic::common::bindings::bind_net(m);
  pymergetic::common::bindings::bind_objects(m);
  pymergetic::common::bindings::bind_runtime(m);
  pymergetic::common::bindings::bind_session(m);
}


