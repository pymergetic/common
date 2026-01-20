#include <nanobind/stl/shared_ptr.h>
#include <nanobind/nanobind.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/string.h>

#include <pymergetic/common/runtime/__init__.hpp>
#include <pymergetic/common/exceptions/__init__.hpp>
#include <pymergetic/common/net/__init__.hpp>
#include <pymergetic/common/nb/__init__.hpp>

#include <memory>

namespace nb = nanobind;

namespace pymergetic::common::bindings {

static ::nanobind::object _make_py_exc(const std::exception& e) {
  // Map known typed codec errors to their Python exception classes.
  // Fallback to RuntimeError for unknown exceptions.
  const char* msg = e.what();
  if (dynamic_cast<const pymergetic::common::MagicMismatchError*>(&e) != nullptr) {
    return ::nanobind::module_::import_("pymergetic.common._internal").attr("MagicMismatchError")(msg);
  }
  if (dynamic_cast<const pymergetic::common::EndOfStreamError*>(&e) != nullptr) {
    return ::nanobind::module_::import_("pymergetic.common._internal").attr("EndOfStreamError")(msg);
  }
  if (dynamic_cast<const pymergetic::common::CodecError*>(&e) != nullptr) {
    return ::nanobind::module_::import_("pymergetic.common._internal").attr("CodecError")(msg);
  }
  return ::nanobind::module_::import_("builtins").attr("RuntimeError")(msg);
}

}  // namespace pymergetic::common::bindings

namespace pymergetic::common::bindings {

namespace nb = ::nanobind;

void bind_net(::nanobind::module_& m) {
  // --- Canonical connection info ---
  nb::enum_<pymergetic::common::net::TransportKind>(m, "TransportKind")
      .value("Unknown", pymergetic::common::net::TransportKind::Unknown)
      .value("Uds", pymergetic::common::net::TransportKind::Uds)
      .value("Tcp", pymergetic::common::net::TransportKind::Tcp)
      .value("Libp2pStream", pymergetic::common::net::TransportKind::Libp2pStream);

  nb::enum_<pymergetic::common::net::AuthKind>(m, "AuthKind")
      .value("None", pymergetic::common::net::AuthKind::None)
      .value("UdsPeerCred", pymergetic::common::net::AuthKind::UdsPeerCred)
      .value("TlsMtls", pymergetic::common::net::AuthKind::TlsMtls)
      .value("Libp2pSecure", pymergetic::common::net::AuthKind::Libp2pSecure)
      .value("Psk", pymergetic::common::net::AuthKind::Psk);

  nb::class_<pymergetic::common::net::PeerInfo>(m, "PeerInfo")
      .def(nb::init<>())
      .def_rw("transport", &pymergetic::common::net::PeerInfo::transport)
      .def_rw("auth_kind", &pymergetic::common::net::PeerInfo::auth_kind)
      .def_rw("authenticated", &pymergetic::common::net::PeerInfo::authenticated)
      .def_rw("peer_id", &pymergetic::common::net::PeerInfo::peer_id)
      .def_rw("peer_name", &pymergetic::common::net::PeerInfo::peer_name)
      .def_rw("local", &pymergetic::common::net::PeerInfo::local)
      .def_rw("remote", &pymergetic::common::net::PeerInfo::remote)
      .def_rw("cert_fingerprint", &pymergetic::common::net::PeerInfo::cert_fingerprint)
      .def_rw("cert_pem", &pymergetic::common::net::PeerInfo::cert_pem)
      .def_rw("pubkey", &pymergetic::common::net::PeerInfo::pubkey)
      .def_rw("psk_id", &pymergetic::common::net::PeerInfo::psk_id)
      .def_rw("peer_pid", &pymergetic::common::net::PeerInfo::peer_pid)
      .def_rw("peer_uid", &pymergetic::common::net::PeerInfo::peer_uid)
      .def_rw("peer_gid", &pymergetic::common::net::PeerInfo::peer_gid);

  nb::class_<pymergetic::common::net::Frame>(m, "Frame")
      .def(nb::init<>())
      .def_rw("version", &pymergetic::common::net::Frame::version)
      .def_rw("flags", &pymergetic::common::net::Frame::flags)
      .def_rw("schema_ver", &pymergetic::common::net::Frame::schema_ver)
      .def_rw("type_id", &pymergetic::common::net::Frame::type_id)
      .def_prop_rw(
          "payload",
          [](const pymergetic::common::net::Frame& f) { return nb::bytes(f.payload.data(), f.payload.size()); },
          [](pymergetic::common::net::Frame& f, nb::bytes b) { f.payload.assign(b.c_str(), b.c_str() + b.size()); });

  nb::class_<pymergetic::common::net::UdsStream>(m, "UdsStream")
      .def("peer_info", &pymergetic::common::net::UdsStream::peer_info)
      .def("close", &pymergetic::common::net::UdsStream::close)
      .def("write_async",
           [](pymergetic::common::net::UdsStream& self, nb::bytes data) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             std::string out(data.c_str(), data.size());
             self.async_write(std::move(out),
                              [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                              std::size_t n) mutable {
                                nb::gil_scoped_acquire _gil;
                                if (ec) {
                                  nb::object exc =
                                      nb::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
                                  pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                                } else {
                                  pymergetic::nb::asyncio_bridge::future_set_result(loop, fut,
                                                                                    nb::int_(static_cast<long long>(n)));
                                }
                                loop = nb::object();
                                fut = nb::object();
                              });
             return fut;
           })
      .def("read_exact_async",
           [](pymergetic::common::net::UdsStream& self, std::size_t nbytes) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_read_exact(
                 nbytes, [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                         std::string data) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ec) {
                     nb::object exc = nb::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
                     pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::bytes(data.data(), data.size()));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });

  nb::class_<pymergetic::common::net::UdsDialer>(m, "UdsDialer")
      .def(nb::init<>())
      .def("connect_async",
           [](pymergetic::common::net::UdsDialer& self, std::string path) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_connect(
                 std::move(path),
                 [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                 std::shared_ptr<pymergetic::common::net::UdsStream> stream) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ec) {
                     nb::object exc = nb::module_::import_("builtins").attr("ConnectionError")(ec.message().c_str());
                     pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::cast(stream));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });

  nb::class_<pymergetic::common::net::UdsAcceptor>(m, "UdsAcceptor")
      .def(nb::init<>())
      .def("start", &pymergetic::common::net::UdsAcceptor::start, nb::arg("path"))
      .def("close", &pymergetic::common::net::UdsAcceptor::close)
      .def("accept_async",
           [](pymergetic::common::net::UdsAcceptor& self) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_accept(
                 [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                 std::shared_ptr<pymergetic::common::net::UdsStream> stream) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ec) {
                     nb::object exc = nb::module_::import_("builtins").attr("ConnectionError")(ec.message().c_str());
                     pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::cast(stream));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });

  nb::class_<pymergetic::common::net::TcpStream>(m, "TcpStream")
      .def("peer_info", &pymergetic::common::net::TcpStream::peer_info)
      .def("close", &pymergetic::common::net::TcpStream::close)
      .def("write_async",
           [](pymergetic::common::net::TcpStream& self, nb::bytes data) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             std::string out(data.c_str(), data.size());
             self.async_write(std::move(out),
                              [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                              std::size_t n) mutable {
                                nb::gil_scoped_acquire _gil;
                                if (ec) {
                                  nb::object exc =
                                      nb::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
                                  pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                                } else {
                                  pymergetic::nb::asyncio_bridge::future_set_result(loop, fut,
                                                                                    nb::int_(static_cast<long long>(n)));
                                }
                                loop = nb::object();
                                fut = nb::object();
                              });
             return fut;
           })
      .def("read_exact_async",
           [](pymergetic::common::net::TcpStream& self, std::size_t nbytes) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_read_exact(
                 nbytes, [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                         std::string data) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ec) {
                     nb::object exc = nb::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
                     pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::bytes(data.data(), data.size()));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });

  nb::class_<pymergetic::common::net::TcpDialer>(m, "TcpDialer")
      .def(nb::init<>())
      .def("connect_async",
           [](pymergetic::common::net::TcpDialer& self, std::string host, std::uint16_t port) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_connect(
                 std::move(host), port,
                 [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                 std::shared_ptr<pymergetic::common::net::TcpStream> stream) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ec) {
                     nb::object exc = nb::module_::import_("builtins").attr("ConnectionError")(ec.message().c_str());
                     pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::cast(stream));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });

  nb::class_<pymergetic::common::net::TcpAcceptor>(m, "TcpAcceptor")
      .def(nb::init<>())
      .def("start", &pymergetic::common::net::TcpAcceptor::start, nb::arg("host"), nb::arg("port"))
      .def("close", &pymergetic::common::net::TcpAcceptor::close)
      .def("accept_async",
           [](pymergetic::common::net::TcpAcceptor& self) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_accept(
                 [loop = nb::object(loop), fut = nb::object(fut)](const boost::system::error_code& ec,
                                                                 std::shared_ptr<pymergetic::common::net::TcpStream> stream) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ec) {
                     nb::object exc = nb::module_::import_("builtins").attr("ConnectionError")(ec.message().c_str());
                     pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::cast(stream));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });

  nb::class_<pymergetic::common::net::PmdgChannel>(m, "PmdgChannel")
      .def(nb::init<pymergetic::common::net::UdsStream&>(), nb::keep_alive<1, 2>())
      .def(nb::init<pymergetic::common::net::TcpStream&>(), nb::keep_alive<1, 2>())
      .def("send_async",
           [](pymergetic::common::net::PmdgChannel& self,
              std::uint32_t type_id,
              nb::bytes payload,
              std::uint8_t flags,
              std::uint16_t schema_ver) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             std::string out(payload.c_str(), payload.size());
             self.async_send(
                 type_id, std::move(out), flags, schema_ver,
                 [loop = nb::object(loop), fut = nb::object(fut)](std::exception_ptr ep, std::size_t n) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ep) {
                     try {
                       std::rethrow_exception(ep);
                     } catch (const std::exception& e) {
                       nb::object exc = nb::module_::import_("builtins").attr("RuntimeError")(e.what());
                       pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                     }
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::int_(static_cast<long long>(n)));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           },
           nb::arg("type_id"),
           nb::arg("payload"),
           nb::arg("flags") = 0,
           nb::arg("schema_ver") = 0)
      .def("recv_async",
           [](pymergetic::common::net::PmdgChannel& self) {
             nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
             nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);
             self.async_recv(
                 [loop = nb::object(loop), fut = nb::object(fut)](std::exception_ptr ep,
                                                                 pymergetic::common::net::Frame f) mutable {
                   nb::gil_scoped_acquire _gil;
                   if (ep) {
                     try {
                       std::rethrow_exception(ep);
                     } catch (const std::exception& e) {
                       nb::object exc = _make_py_exc(e);
                       pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                     }
                   } else {
                     pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::cast(f));
                   }
                   loop = nb::object();
                   fut = nb::object();
                 });
             return fut;
           });
}

}  // namespace pymergetic::common::bindings


