#include <nanobind/nanobind.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/string.h>

#include <pymergetic/common/runtime/__init__.hpp>
#include <pymergetic/common/codec/__init__.hpp>
#include <pymergetic/common/exceptions/__init__.hpp>
#include <pymergetic/common/net/__init__.hpp>
#include <pymergetic/common/nb/__init__.hpp>

#include <boost/asio/local/stream_protocol.hpp>
#include <boost/asio/read.hpp>
#include <boost/asio/write.hpp>

#if defined(__linux__)
#include <sys/socket.h>
#include <sys/types.h>
#endif

#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace nb = nanobind;

namespace pymergetic::net {

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

struct Frame {
  std::uint8_t version = 1;
  std::uint8_t flags = 0;
  std::uint16_t schema_ver = 0;
  std::uint32_t type_id = 0;
  std::string payload;  // raw bytes
};

class UdsStream : public std::enable_shared_from_this<UdsStream> {
public:
  explicit UdsStream(std::shared_ptr<pymergetic::common::AsioRuntime> rt)
      : rt_(std::move(rt)), sock_(rt_->io()) {}

  pymergetic::common::net::PeerInfo peer_info() const { return peer_info_; }

  void close() {
    boost::system::error_code ec;
    sock_.close(ec);
  }

  ::nanobind::object write_async(::nanobind::bytes data) {
    ::nanobind::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
    ::nanobind::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);

    auto self = shared_from_this();
    auto buf = std::make_shared<std::string>(data.c_str(), data.size());

    boost::asio::async_write(
        sock_, boost::asio::buffer(*buf),
        [loop = ::nanobind::object(loop), fut = ::nanobind::object(fut), buf, self](const boost::system::error_code& ec,
                                                                                   std::size_t n) mutable {
          ::nanobind::gil_scoped_acquire _gil;
          if (ec) {
            ::nanobind::object exc = ::nanobind::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
            pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
          } else {
            pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, ::nanobind::int_(static_cast<long long>(n)));
          }
          loop = ::nanobind::object();
          fut = ::nanobind::object();
        });

    return fut;
  }

  ::nanobind::object read_exact_async(std::size_t nbytes) {
    ::nanobind::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
    ::nanobind::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);

    auto self = shared_from_this();
    auto buf = std::make_shared<std::vector<char>>(nbytes);

    boost::asio::async_read(
        sock_, boost::asio::buffer(*buf),
        [loop = ::nanobind::object(loop), fut = ::nanobind::object(fut), buf, self](const boost::system::error_code& ec,
                                                                                   std::size_t n) mutable {
          ::nanobind::gil_scoped_acquire _gil;
          if (ec) {
            ::nanobind::object exc = ::nanobind::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
            pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
          } else {
            pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, ::nanobind::bytes(buf->data(), n));
          }
          loop = ::nanobind::object();
          fut = ::nanobind::object();
        });

    return fut;
  }

  boost::asio::local::stream_protocol::socket& socket() { return sock_; }

  void set_connected_path(std::string path) {
    peer_info_.transport = pymergetic::common::net::TransportKind::Uds;
    peer_info_.local = "unix:" + path;
    peer_info_.remote = "unix";

#if defined(__linux__)
    // Derive OS identity from UDS peer credentials (transport-provided identity).
    struct ucred cred;
    socklen_t len = sizeof(cred);
    if (::getsockopt(sock_.native_handle(), SOL_SOCKET, SO_PEERCRED, &cred, &len) == 0 && len == sizeof(cred)) {
      peer_info_.peer_pid = static_cast<std::int32_t>(cred.pid);
      peer_info_.peer_uid = static_cast<std::int32_t>(cred.uid);
      peer_info_.peer_gid = static_cast<std::int32_t>(cred.gid);
      peer_info_.auth_kind = pymergetic::common::net::AuthKind::UdsPeerCred;
      peer_info_.authenticated = true;
      peer_info_.peer_id = "uid:" + std::to_string(peer_info_.peer_uid);
      peer_info_.remote = "uid:" + std::to_string(peer_info_.peer_uid) + " pid:" + std::to_string(peer_info_.peer_pid);
    } else {
      peer_info_.auth_kind = pymergetic::common::net::AuthKind::None;
      peer_info_.authenticated = false;
      peer_info_.peer_id.clear();
    }
#else
    peer_info_.auth_kind = pymergetic::common::net::AuthKind::None;
    peer_info_.authenticated = false;
    peer_info_.peer_id.clear();
#endif
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
  boost::asio::local::stream_protocol::socket sock_;
  pymergetic::common::net::PeerInfo peer_info_{};
};

class UdsDialer {
public:
  UdsDialer() : rt_(std::make_shared<pymergetic::common::AsioRuntime>()) { rt_->start(); }

  ::nanobind::object connect_async(std::string path) {
    ::nanobind::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
    ::nanobind::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);

    auto stream = std::make_shared<UdsStream>(rt_);
    boost::asio::local::stream_protocol::endpoint ep(path);

    stream->socket().async_connect(
        ep, [loop = ::nanobind::object(loop), fut = ::nanobind::object(fut), stream, path = std::move(path)](const boost::system::error_code& ec) mutable {
          ::nanobind::gil_scoped_acquire _gil;
          if (ec) {
            ::nanobind::object exc = ::nanobind::module_::import_("builtins").attr("ConnectionError")(ec.message().c_str());
            pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
          } else {
            stream->set_connected_path(path);
            pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, ::nanobind::cast(stream));
          }
          loop = ::nanobind::object();
          fut = ::nanobind::object();
        });

    return fut;
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
};

class PmdgChannel {
public:
  explicit PmdgChannel(std::shared_ptr<UdsStream> s) : s_(std::move(s)) {}

  ::nanobind::object send_async(std::uint32_t type_id, ::nanobind::bytes payload, std::uint8_t flags = 0, std::uint16_t schema_ver = 0) {
    std::string out;
    pymergetic::common::codec::append_header(out, type_id, static_cast<std::uint32_t>(payload.size()), flags, schema_ver);
    out.append(payload.c_str(), payload.size());
    return s_->write_async(::nanobind::bytes(out.data(), out.size()));
  }

  ::nanobind::object recv_async() {
    ::nanobind::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
    ::nanobind::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);

    auto s = s_;
    auto header = std::make_shared<std::array<char, 16>>();

    boost::asio::async_read(
        s->socket(), boost::asio::buffer(*header),
        [loop = ::nanobind::object(loop), fut = ::nanobind::object(fut), s, header](const boost::system::error_code& ec,
                                                                                   std::size_t /*n*/) mutable {
          if (ec) {
            ::nanobind::gil_scoped_acquire _gil;
            ::nanobind::object exc = ::nanobind::module_::import_("builtins").attr("RuntimeError")(ec.message().c_str());
            pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
            loop = ::nanobind::object();
            fut = ::nanobind::object();
            return;
          }

          try {
            const char* hp = header->data();
            const std::size_t hn = header->size();
            const std::uint32_t payload_len = pymergetic::common::codec::read_u32_le(hp, hn, 12);

            auto payload = std::make_shared<std::vector<char>>(static_cast<std::size_t>(payload_len));
            boost::asio::async_read(
                s->socket(), boost::asio::buffer(*payload),
                [loop = ::nanobind::object(loop), fut = ::nanobind::object(fut), header, payload](const boost::system::error_code& ec2,
                                                                                                  std::size_t /*n2*/) mutable {
                  ::nanobind::gil_scoped_acquire _gil;
                  if (ec2) {
                    ::nanobind::object exc = ::nanobind::module_::import_("builtins").attr("RuntimeError")(ec2.message().c_str());
                    pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                    loop = ::nanobind::object();
                    fut = ::nanobind::object();
                    return;
                  }

                  try {
                    std::string full;
                    full.reserve(16 + payload->size());
                    full.append(header->data(), header->size());
                    full.append(payload->data(), payload->size());

                    const auto h = pymergetic::common::codec::read_header(full.data(), full.size());

                    Frame f;
                    f.version = h.version;
                    f.flags = h.flags;
                    f.schema_ver = h.schema_ver;
                    f.type_id = h.type_id;
                    f.payload.assign(full.data() + static_cast<std::ptrdiff_t>(h.payload_off),
                                     full.data() + static_cast<std::ptrdiff_t>(h.payload_off + h.payload_len));

                    pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, ::nanobind::cast(f));
                  } catch (const std::exception& e) {
                    ::nanobind::object exc = _make_py_exc(e);
                    pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
                  }

                  loop = ::nanobind::object();
                  fut = ::nanobind::object();
                });
          } catch (const std::exception& e) {
            ::nanobind::gil_scoped_acquire _gil;
            ::nanobind::object exc = _make_py_exc(e);
            pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
            loop = ::nanobind::object();
            fut = ::nanobind::object();
          }
        });

    return fut;
  }

private:
  std::shared_ptr<UdsStream> s_;
};

}  // namespace pymergetic::net

namespace pymergetic::common::bindings {

namespace nb = ::nanobind;

void bind_net(::nanobind::module_& m) {
  // Exception mapping (codec)
  nb::exception<pymergetic::common::CodecError>(m, "CodecError");
  nb::exception<pymergetic::common::EndOfStreamError>(m, "EndOfStreamError");
  nb::exception<pymergetic::common::MagicMismatchError>(m, "MagicMismatchError");

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

  nb::class_<pymergetic::net::Frame>(m, "Frame")
      .def(nb::init<>())
      .def_rw("version", &pymergetic::net::Frame::version)
      .def_rw("flags", &pymergetic::net::Frame::flags)
      .def_rw("schema_ver", &pymergetic::net::Frame::schema_ver)
      .def_rw("type_id", &pymergetic::net::Frame::type_id)
      .def_prop_rw(
          "payload",
          [](const pymergetic::net::Frame& f) { return nb::bytes(f.payload.data(), f.payload.size()); },
          [](pymergetic::net::Frame& f, nb::bytes b) { f.payload.assign(b.c_str(), b.c_str() + b.size()); });

  nb::class_<pymergetic::net::UdsStream>(m, "UdsStream")
      .def("peer_info", &pymergetic::net::UdsStream::peer_info)
      .def("close", &pymergetic::net::UdsStream::close)
      .def("write_async", &pymergetic::net::UdsStream::write_async)
      .def("read_exact_async", &pymergetic::net::UdsStream::read_exact_async);

  nb::class_<pymergetic::net::UdsDialer>(m, "UdsDialer")
      .def(nb::init<>())
      .def("connect_async", &pymergetic::net::UdsDialer::connect_async);

  nb::class_<pymergetic::net::PmdgChannel>(m, "PmdgChannel")
      .def(nb::init<std::shared_ptr<pymergetic::net::UdsStream>>())
      .def("send_async", &pymergetic::net::PmdgChannel::send_async, nb::arg("type_id"), nb::arg("payload"),
           nb::arg("flags") = 0, nb::arg("schema_ver") = 0)
      .def("recv_async", &pymergetic::net::PmdgChannel::recv_async);
}

}  // namespace pymergetic::common::bindings


