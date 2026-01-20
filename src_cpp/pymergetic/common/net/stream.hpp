#pragma once

#include <pymergetic/common/net/peer_info.hpp>

#include <boost/system/error_code.hpp>

#include <cstddef>
#include <functional>
#include <memory>
#include <string>

namespace pymergetic::common::net {

class Stream {
public:
  using ReadHandler = std::function<void(const boost::system::error_code&, std::string)>;
  using WriteHandler = std::function<void(const boost::system::error_code&, std::size_t)>;

  virtual ~Stream() = default;

  virtual const PeerInfo& peer_info() const = 0;
  virtual void close() = 0;
  virtual void async_read_exact(std::size_t nbytes, ReadHandler handler) = 0;
  virtual void async_write(std::string data, WriteHandler handler) = 0;
};

}  // namespace pymergetic::common::net

