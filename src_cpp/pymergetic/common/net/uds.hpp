#pragma once

#include <pymergetic/common/net/stream.hpp>
#include <pymergetic/common/runtime/__init__.hpp>

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

namespace pymergetic::common::net {

class UdsStream : public Stream, public std::enable_shared_from_this<UdsStream> {
public:
  explicit UdsStream(std::shared_ptr<pymergetic::common::AsioRuntime> rt)
      : rt_(std::move(rt)), sock_(rt_->io()) {}

  const PeerInfo& peer_info() const override { return peer_info_; }

  void close() override {
    boost::system::error_code ec;
    sock_.close(ec);
  }

  void async_write(std::string data, WriteHandler handler) override {
    auto buf = std::make_shared<std::string>(std::move(data));
    boost::asio::async_write(
        sock_, boost::asio::buffer(*buf),
        [buf, handler = std::move(handler)](const boost::system::error_code& ec, std::size_t n) mutable {
          handler(ec, n);
        });
  }

  void async_read_exact(std::size_t nbytes, ReadHandler handler) override {
    auto buf = std::make_shared<std::vector<char>>(nbytes);
    boost::asio::async_read(
        sock_, boost::asio::buffer(*buf),
        [buf, handler = std::move(handler)](const boost::system::error_code& ec, std::size_t n) mutable {
          if (ec) {
            handler(ec, std::string());
            return;
          }
          handler(ec, std::string(buf->data(), n));
        });
  }

  boost::asio::local::stream_protocol::socket& socket() { return sock_; }

  void set_connected_path(std::string path) {
    peer_info_.transport = TransportKind::Uds;
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
      peer_info_.auth_kind = AuthKind::UdsPeerCred;
      peer_info_.authenticated = true;
      peer_info_.peer_id = "uid:" + std::to_string(peer_info_.peer_uid);
      peer_info_.remote = "uid:" + std::to_string(peer_info_.peer_uid) + " pid:" + std::to_string(peer_info_.peer_pid);
    } else {
      peer_info_.auth_kind = AuthKind::None;
      peer_info_.authenticated = false;
      peer_info_.peer_id.clear();
    }
#else
    peer_info_.auth_kind = AuthKind::None;
    peer_info_.authenticated = false;
    peer_info_.peer_id.clear();
#endif
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
  boost::asio::local::stream_protocol::socket sock_;
  PeerInfo peer_info_{};
};

class UdsDialer {
public:
  using ConnectHandler = std::function<void(const boost::system::error_code&, std::shared_ptr<UdsStream>)>;

  UdsDialer() : rt_(std::make_shared<pymergetic::common::AsioRuntime>()) { rt_->start(); }

  void async_connect(std::string path, ConnectHandler handler) {
    auto stream = std::make_shared<UdsStream>(rt_);
    boost::asio::local::stream_protocol::endpoint ep(path);
    stream->socket().async_connect(
        ep, [stream, path = std::move(path), handler = std::move(handler)](const boost::system::error_code& ec) mutable {
          if (ec) {
            handler(ec, nullptr);
          } else {
            stream->set_connected_path(path);
            handler(ec, stream);
          }
        });
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
};

}  // namespace pymergetic::common::net

