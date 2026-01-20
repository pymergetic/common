#pragma once

#include <pymergetic/common/net/stream.hpp>
#include <pymergetic/common/runtime/__init__.hpp>

#include <boost/asio/connect.hpp>
#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/read.hpp>
#include <boost/asio/write.hpp>

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace pymergetic::common::net {

class TcpStream : public Stream, public std::enable_shared_from_this<TcpStream> {
public:
  explicit TcpStream(std::shared_ptr<pymergetic::common::AsioRuntime> rt)
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

  boost::asio::ip::tcp::socket& socket() { return sock_; }

  void set_connected_endpoint() {
    peer_info_.transport = TransportKind::Tcp;
    peer_info_.auth_kind = AuthKind::None;
    peer_info_.authenticated = false;
    peer_info_.peer_id.clear();
    boost::system::error_code ec;
    auto local = sock_.local_endpoint(ec);
    if (!ec) {
      peer_info_.local = "tcp:" + local.address().to_string() + ":" + std::to_string(local.port());
    }
    auto remote = sock_.remote_endpoint(ec);
    if (!ec) {
      peer_info_.remote = "tcp:" + remote.address().to_string() + ":" + std::to_string(remote.port());
    }
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
  boost::asio::ip::tcp::socket sock_;
  PeerInfo peer_info_{};
};

class TcpDialer {
public:
  using ConnectHandler = std::function<void(const boost::system::error_code&, std::shared_ptr<TcpStream>)>;

  TcpDialer() : rt_(std::make_shared<pymergetic::common::AsioRuntime>()) { rt_->start(); }

  void async_connect(std::string host, std::uint16_t port, ConnectHandler handler) {
    auto stream = std::make_shared<TcpStream>(rt_);
    auto resolver = std::make_shared<boost::asio::ip::tcp::resolver>(rt_->io());
    resolver->async_resolve(
        host, std::to_string(port),
        [stream, resolver, handler = std::move(handler)](const boost::system::error_code& ec,
                                                         boost::asio::ip::tcp::resolver::results_type results) mutable {
          if (ec) {
            handler(ec, nullptr);
            return;
          }
          boost::asio::async_connect(
              stream->socket(), results,
              [stream, handler = std::move(handler)](const boost::system::error_code& ec2,
                                                     const boost::asio::ip::tcp::endpoint&) mutable {
                if (ec2) {
                  handler(ec2, nullptr);
                  return;
                }
                stream->set_connected_endpoint();
                handler(ec2, stream);
              });
        });
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
};

}  // namespace pymergetic::common::net

