#pragma once

#include <nanobind/nanobind.h>

namespace pymergetic::nb::asyncio_bridge {

namespace nb = nanobind;

// Thread-safe completion helpers for asyncio.Future from non-Python threads
// (e.g. Boost.Asio io_context thread).
inline void future_set_result(nb::object loop, nb::object future, nb::object value) {
  nb::gil_scoped_acquire _gil;
  loop.attr("call_soon_threadsafe")(future.attr("set_result"), value);
}

inline void future_set_exception(nb::object loop, nb::object future, nb::object exc) {
  nb::gil_scoped_acquire _gil;
  loop.attr("call_soon_threadsafe")(future.attr("set_exception"), exc);
}

inline nb::object get_running_loop() {
  nb::module_ asyncio = nb::module_::import_("asyncio");
  return asyncio.attr("get_running_loop")();
}

inline nb::object create_future(nb::object loop) {
  return loop.attr("create_future")();
}

}  // namespace pymergetic::nb::asyncio_bridge


