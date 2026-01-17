#pragma once

#include <boost/asio/executor_work_guard.hpp>
#include <boost/asio/io_context.hpp>

#include <atomic>
#include <thread>

namespace pymergetic::common {

/// Minimal Boost.Asio runtime (Level 1 / Python-free).
///
/// - Owns an io_context + work guard + a dedicated thread.
/// - Designed as a shared building block for native services (CppObject) that
///   want consistent lifecycle behavior across modules.
class AsioRuntime {
public:
  AsioRuntime() : io_(1) {}

  AsioRuntime(const AsioRuntime&) = delete;
  AsioRuntime& operator=(const AsioRuntime&) = delete;

  ~AsioRuntime() { stop(); }

  void start() {
    bool expected = false;
    if (!running_.compare_exchange_strong(expected, true)) {
      return;
    }
    work_.emplace(boost::asio::make_work_guard(io_));
    thread_ = std::thread([this]() { io_.run(); });
  }

  void stop() {
    bool expected = true;
    if (!running_.compare_exchange_strong(expected, false)) {
      return;
    }
    if (work_) {
      work_.reset();
    }
    io_.stop();
    if (thread_.joinable()) {
      thread_.join();
    }
    io_.restart();
  }

  boost::asio::io_context& io() { return io_; }

private:
  boost::asio::io_context io_;
  std::optional<boost::asio::executor_work_guard<boost::asio::io_context::executor_type>> work_;
  std::thread thread_;
  std::atomic<bool> running_{false};
};

}  // namespace pymergetic::common


