#include <nanobind/nanobind.h>
#include <nanobind/stl/map.h>
#include <nanobind/stl/set.h>
#include <nanobind/stl/string.h>

#include <pymergetic/common/session/__init__.hpp>

namespace pymergetic::common::bindings {

namespace nb = ::nanobind;

void bind_session(::nanobind::module_& m) {
  nb::class_<pymergetic::common::session::AuthPolicy>(m, "AuthPolicy")
      .def(nb::init<>())
      .def_rw("allow_anonymous", &pymergetic::common::session::AuthPolicy::allow_anonymous)
      .def_rw("require_transport_authenticated",
              &pymergetic::common::session::AuthPolicy::require_transport_authenticated)
      .def_rw("allow_uids", &pymergetic::common::session::AuthPolicy::allow_uids)
      .def_rw("allow_peer_ids", &pymergetic::common::session::AuthPolicy::allow_peer_ids)
      .def("allow_uid", [](pymergetic::common::session::AuthPolicy& p, std::int32_t uid) { p.allow_uids.insert(uid); })
      .def("allow_peer_id",
           [](pymergetic::common::session::AuthPolicy& p, const std::string& peer_id) { p.allow_peer_ids.insert(peer_id); });

  nb::class_<pymergetic::common::session::SessionContext>(m, "SessionContext")
      .def(nb::init<>())
      .def_rw("peer", &pymergetic::common::session::SessionContext::peer)
      .def_rw("accepted", &pymergetic::common::session::SessionContext::accepted)
      .def_rw("authenticated", &pymergetic::common::session::SessionContext::authenticated)
      .def_rw("principal", &pymergetic::common::session::SessionContext::principal)
      .def_rw("session_id", &pymergetic::common::session::SessionContext::session_id)
      .def_rw("claims", &pymergetic::common::session::SessionContext::claims);

  m.def("apply_policy", &pymergetic::common::session::apply_policy, nb::arg("peer"), nb::arg("policy"));
  m.def("make_session", &pymergetic::common::session::make_session, nb::arg("peer"), nb::arg("policy"),
        nb::arg("session_id") = "");
}

}  // namespace pymergetic::common::bindings

