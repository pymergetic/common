#pragma once

#include <pymergetic/common/codec/__init__.hpp>
#include <pymergetic/common/net/stream.hpp>
#include <pymergetic/common/net/tcp.hpp>
#include <pymergetic/common/net/uds.hpp>

#include <boost/system/error_code.hpp>

#include <array>
#include <cstdint>
#include <exception>
#include <memory>
#include <string>
#include <utility>

namespace pymergetic::common::net {

struct Frame {
  std::uint8_t version = 1;
  std::uint8_t flags = 0;
  std::uint16_t schema_ver = 0;
  std::uint32_t type_id = 0;
  std::string payload;
};

class PmdgChannel {
public:
  using SendHandler = std::function<void(std::exception_ptr, std::size_t)>;
  using RecvHandler = std::function<void(std::exception_ptr, Frame)>;

  explicit PmdgChannel(std::shared_ptr<Stream> s) : s_(std::move(s)) {}
  explicit PmdgChannel(std::shared_ptr<UdsStream> s)
      : s_(std::static_pointer_cast<Stream>(std::move(s))) {}
  explicit PmdgChannel(UdsStream& s)
      : s_(std::shared_ptr<Stream>(&s, [](Stream*) {})) {}
  explicit PmdgChannel(std::shared_ptr<TcpStream> s)
      : s_(std::static_pointer_cast<Stream>(std::move(s))) {}
  explicit PmdgChannel(TcpStream& s)
      : s_(std::shared_ptr<Stream>(&s, [](Stream*) {})) {}

  void async_send(std::uint32_t type_id,
                  std::string payload,
                  std::uint8_t flags,
                  std::uint16_t schema_ver,
                  SendHandler handler) {
    std::string out;
    pymergetic::common::codec::append_header(out, type_id, static_cast<std::uint32_t>(payload.size()), flags, schema_ver);
    out.append(payload.data(), payload.size());
    s_->async_write(
        std::move(out),
        [handler = std::move(handler)](const boost::system::error_code& ec, std::size_t n) mutable {
          if (ec) {
            handler(std::make_exception_ptr(std::runtime_error(ec.message())), 0);
            return;
          }
          handler(nullptr, n);
        });
  }

  void async_recv(RecvHandler handler) {
    auto s = s_;
    s_->async_read_exact(
        16, [s, handler = std::move(handler)](const boost::system::error_code& ec, std::string header) mutable {
          if (ec) {
            handler(std::make_exception_ptr(std::runtime_error(ec.message())), Frame{});
            return;
          }
          try {
            const std::uint32_t payload_len =
                pymergetic::common::codec::read_u32_le(header.data(), header.size(), 12);
            s->async_read_exact(
                payload_len,
                [header = std::move(header), handler = std::move(handler)](const boost::system::error_code& ec2,
                                                                          std::string payload) mutable {
                  if (ec2) {
                    handler(std::make_exception_ptr(std::runtime_error(ec2.message())), Frame{});
                    return;
                  }
                  try {
                    std::string full;
                    full.reserve(16 + payload.size());
                    full.append(header.data(), header.size());
                    full.append(payload.data(), payload.size());
                    const auto h = pymergetic::common::codec::read_header(full.data(), full.size());
                    Frame f;
                    f.version = h.version;
                    f.flags = h.flags;
                    f.schema_ver = h.schema_ver;
                    f.type_id = h.type_id;
                    f.payload.assign(full.data() + static_cast<std::ptrdiff_t>(h.payload_off),
                                     full.data() + static_cast<std::ptrdiff_t>(h.payload_off + h.payload_len));
                    handler(nullptr, std::move(f));
                  } catch (...) {
                    handler(std::current_exception(), Frame{});
                  }
                });
          } catch (...) {
            handler(std::current_exception(), Frame{});
          }
        });
  }

private:
  std::shared_ptr<Stream> s_;
};

}  // namespace pymergetic::common::net

