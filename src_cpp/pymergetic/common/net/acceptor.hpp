#pragma once

#include <pymergetic/common/net/stream.hpp>
#include <pymergetic/common/net/tcp.hpp>
#include <pymergetic/common/net/uds.hpp>
#include <pymergetic/common/runtime/__init__.hpp>

#include <boost/asio/ip/tcp.hpp>
#include <boost/asio/local/stream_protocol.hpp>

#include <cstdio>
#include <functional>
#include <memory>
#include <string>

namespace pymergetic::common::net {

class UdsAcceptor {
public:
  using AcceptHandler = std::function<void(const boost::system::error_code&, std::shared_ptr<UdsStream>)>;

  UdsAcceptor() : rt_(std::make_shared<pymergetic::common::AsioRuntime>()), acceptor_(rt_->io()) { rt_->start(); }

  void start(std::string path) {
    path_ = std::move(path);
    std::remove(path_.c_str());
    boost::asio::local::stream_protocol::endpoint ep(path_);
    acceptor_.open(ep.protocol());
    acceptor_.bind(ep);
    acceptor_.listen();
  }

  void async_accept(AcceptHandler handler) {
    auto stream = std::make_shared<UdsStream>(rt_);
    acceptor_.async_accept(
        stream->socket(),
        [stream, handler = std::move(handler), path = path_](const boost::system::error_code& ec) mutable {
          if (!ec) {
            stream->set_connected_path(path);
          }
          handler(ec, stream);
        });
  }

  void close() {
    boost::system::error_code ec;
    acceptor_.close(ec);
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
  boost::asio::local::stream_protocol::acceptor acceptor_;
  std::string path_;
};

class TcpAcceptor {
public:
  using AcceptHandler = std::function<void(const boost::system::error_code&, std::shared_ptr<TcpStream>)>;

  TcpAcceptor() : rt_(std::make_shared<pymergetic::common::AsioRuntime>()), acceptor_(rt_->io()) { rt_->start(); }

  void start(const std::string& host, std::uint16_t port) {
    boost::asio::ip::tcp::endpoint ep{boost::asio::ip::make_address(host), port};
    acceptor_.open(ep.protocol());
    acceptor_.set_option(boost::asio::ip::tcp::acceptor::reuse_address(true));
    acceptor_.bind(ep);
    acceptor_.listen();
  }

  void async_accept(AcceptHandler handler) {
    auto stream = std::make_shared<TcpStream>(rt_);
    acceptor_.async_accept(
        stream->socket(),
        [stream, handler = std::move(handler)](const boost::system::error_code& ec) mutable {
          if (!ec) {
            stream->set_connected_endpoint();
          }
          handler(ec, stream);
        });
  }

  void close() {
    boost::system::error_code ec;
    acceptor_.close(ec);
  }

private:
  std::shared_ptr<pymergetic::common::AsioRuntime> rt_;
  boost::asio::ip::tcp::acceptor acceptor_;
};

}  // namespace pymergetic::common::net

