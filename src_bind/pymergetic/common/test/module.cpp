#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <pymergetic/common/nb/__init__.hpp>

#include <pymergetic/common/codec/__init__.hpp>
#include <pymergetic/common/exceptions/__init__.hpp>

#include <boost/asio/io_context.hpp>
#include <boost/asio/post.hpp>
#include <boost/asio/steady_timer.hpp>
#include <boost/system/error_code.hpp>

#include <chrono>
#include <thread>

namespace nb = nanobind;

namespace pymergetic::common {

struct NativePeerInfo {
  std::string peer_id;
  std::vector<std::string> addresses;
};

struct NativeOptional {
  std::optional<std::string> name;
};

struct NativeAddress {
  std::string ip;
};

struct NativePeerNested;

struct NativeAddressVecView {
  NativePeerNested* owner{};

  std::size_t size() const;
  NativeAddress& at(std::size_t i);
  void set(std::size_t i, NativeAddress v);
  void append(NativeAddress v);
  void erase(std::size_t i);
  void clear();
};

struct NativePeerNested {
  std::string peer_id;
  NativeAddress main_address;
  std::vector<NativeAddress> addresses_storage;
  NativeAddressVecView addresses;

  NativePeerNested() {
    addresses.owner = this;
  }

  NativePeerNested(const NativePeerNested& other)
      : peer_id(other.peer_id),
        main_address(other.main_address),
        addresses_storage(other.addresses_storage) {
    addresses.owner = this;
  }

  NativePeerNested(NativePeerNested&& other) noexcept
      : peer_id(std::move(other.peer_id)),
        main_address(std::move(other.main_address)),
        addresses_storage(std::move(other.addresses_storage)) {
    addresses.owner = this;
  }

  NativePeerNested& operator=(const NativePeerNested& other) {
    if (this == &other) return *this;
    peer_id = other.peer_id;
    main_address = other.main_address;
    addresses_storage = other.addresses_storage;
    addresses.owner = this;
    return *this;
  }

  NativePeerNested& operator=(NativePeerNested&& other) noexcept {
    if (this == &other) return *this;
    peer_id = std::move(other.peer_id);
    main_address = std::move(other.main_address);
    addresses_storage = std::move(other.addresses_storage);
    addresses.owner = this;
    return *this;
  }
};

struct PacketPayload {
  std::vector<std::uint8_t> data;
};

struct NetworkPacket {
  std::string id;
  double timestamp{};
  std::shared_ptr<PacketPayload> payload;
};

inline std::size_t NativeAddressVecView::size() const { return owner->addresses_storage.size(); }
inline NativeAddress& NativeAddressVecView::at(std::size_t i) { return owner->addresses_storage.at(i); }
inline void NativeAddressVecView::set(std::size_t i, NativeAddress v) { owner->addresses_storage.at(i) = std::move(v); }
inline void NativeAddressVecView::append(NativeAddress v) { owner->addresses_storage.push_back(std::move(v)); }
inline void NativeAddressVecView::erase(std::size_t i) { owner->addresses_storage.erase(owner->addresses_storage.begin() + static_cast<std::ptrdiff_t>(i)); }
inline void NativeAddressVecView::clear() { owner->addresses_storage.clear(); }

}  // namespace pymergetic::common

NB_MODULE(_test_internal, m) {
  m.doc() = "pymergetic-common test extension (nanobind)";

  // --- Exception mapping (C++ -> Python) ---
  nb::exception<pymergetic::common::CodecError>(m, "CodecError");
  nb::exception<pymergetic::common::EndOfStreamError>(m, "EndOfStreamError");
  nb::exception<pymergetic::common::MagicMismatchError>(m, "MagicMismatchError");

  m.def("add", [](int a, int b) { return a + b; });

  // Boost.Asio smoke: ensure headers compile and async timer runs.
  m.def("boost_asio_timer_fires", []() {
    boost::asio::io_context io(1);
    boost::asio::steady_timer t(io);
    bool fired = false;
    t.expires_after(std::chrono::milliseconds(1));
    t.async_wait([&](const boost::system::error_code& ec) { fired = !ec; });
    io.run();
    return fired;
  });

  // Standardized Asio -> asyncio.Future bridge example.
  // Returns an awaitable Future that resolves to a+b from an Asio thread.
  m.def("boost_asio_async_add", [](int a, int b) -> nb::object {
    nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
    nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);

    // Run a tiny Asio task on a dedicated thread and resolve the Future.
    std::thread([loop = nb::object(loop), fut = nb::object(fut), a, b]() mutable {
      boost::asio::io_context io(1);
      boost::asio::post(io, [loop = std::move(loop), fut = std::move(fut), a, b]() mutable {
        // IMPORTANT: ensure any decref of `nb::object` happens while holding the GIL.
        // The lambda object (and its captures) will be destroyed by Asio on this thread
        // after the handler runs. We therefore "drain" the captures under the GIL.
        nb::gil_scoped_acquire _gil;
        try {
          pymergetic::nb::asyncio_bridge::future_set_result(loop, fut, nb::int_(a + b));
        } catch (const std::exception& e) {
          nb::object exc = nb::module_::import_("builtins").attr("RuntimeError")(e.what());
          pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
        }
        // Drain captures under GIL so the eventual lambda destruction is safe.
        loop = nb::object();
        fut = nb::object();
      });
      io.run();
    }).detach();

    return fut;
  });

  // Async exception path: returns an awaitable Future that raises RuntimeError.
  m.def("boost_asio_async_fail", [](const std::string& msg) -> nb::object {
    nb::object loop = pymergetic::nb::asyncio_bridge::get_running_loop();
    nb::object fut = pymergetic::nb::asyncio_bridge::create_future(loop);

    std::thread([loop = nb::object(loop), fut = nb::object(fut), msg]() mutable {
      boost::asio::io_context io(1);
      boost::asio::post(io, [loop = std::move(loop), fut = std::move(fut), msg]() mutable {
        nb::gil_scoped_acquire _gil;
        nb::object exc = nb::module_::import_("builtins").attr("RuntimeError")(msg.c_str());
        pymergetic::nb::asyncio_bridge::future_set_exception(loop, fut, std::move(exc));
        loop = nb::object();
        fut = nb::object();
      });
      io.run();
    }).detach();

    return fut;
  });

  // ---- CppObject / PyObject pattern smoke ----
  nb::class_<pymergetic::nb::CppObject>(m, "CppObject")
      .def("to_dict", &pymergetic::nb::CppObject::to_dict)
      .def("__repr__", &pymergetic::nb::CppObject::repr);

  // ---- CppDataObject / PyDataObject pattern smoke ----
  nb::class_<pymergetic::nb::CppDataObject, pymergetic::nb::CppObject>(m, "CppDataObject")
      .def("serialize", &pymergetic::nb::CppDataObject::serialize)
      .def("to_dict", &pymergetic::nb::CppDataObject::to_dict)
      .def("__repr__", &pymergetic::nb::CppDataObject::repr);

  struct NetworkService : public pymergetic::nb::CppObject {
    std::string status = "disconnected";
    void connect(std::string url) { status = "connected:" + url; }
    std::string repr() const override { return "<NetworkService>"; }
    nb::dict to_dict() const override {
      nb::dict d;
      d["status"] = status;
      return d;
    }
  };

  nb::class_<NetworkService, pymergetic::nb::CppObject>(m, "NetworkService")
      .def("connect", &NetworkService::connect)
      .def("to_dict", &NetworkService::to_dict)
      .def("__repr__", &NetworkService::repr);

  m.def("make_network_service", []() { return std::make_shared<NetworkService>(); });

  // shared_ptr lifetime proof: C++ can hold a reference independent of Python.
  static std::shared_ptr<NetworkService> _held_service;
  m.def("cpp_hold_network_service", [](std::shared_ptr<NetworkService> s) { _held_service = std::move(s); });
  m.def("cpp_get_held_network_service", []() { return _held_service; });
  m.def("cpp_clear_held_network_service", []() { _held_service.reset(); });

  // Example pure data object (idempotent bytes roundtrip).
  struct DataPoint : public pymergetic::nb::CppDataObject {
    std::int32_t a = 0;
    std::string b;

    std::string repr() const override { return "<DataPoint>"; }

    nb::dict to_dict() const override {
      nb::dict d;
      d["a"] = a;
      d["b"] = b;
      return d;
    }

    std::string serialize_bytes() const override {
      constexpr std::uint32_t k_type_id = pymergetic::common::codec::type_id("pymergetic.common.DataPoint");
      // Payload format (versioned by outer header):
      //   [i32 little][u32 len][bytes]
      std::string payload;
      pymergetic::common::codec::append_i32_le(payload, a);
      pymergetic::common::codec::append_u32_len_prefixed(payload, b);

      std::string out;
      pymergetic::common::codec::append_header(out, k_type_id, static_cast<std::uint32_t>(payload.size()));
      out.append(payload);
      return out;
    }

    static std::shared_ptr<DataPoint> deserialize(nb::bytes data) {
      constexpr std::uint32_t k_type_id = pymergetic::common::codec::type_id("pymergetic.common.DataPoint");
      const char* p = data.c_str();
      const std::size_t n = data.size();
      const auto h = pymergetic::common::codec::read_header(p, n);
      if (h.type_id != k_type_id) {
        throw pymergetic::common::CodecError("DataPoint: wrong type_id");
      }
      const std::size_t off0 = h.payload_off;
      const std::int32_t a = pymergetic::common::codec::read_i32_le(p, n, off0);
      std::size_t next = 0;
      std::string b = pymergetic::common::codec::read_u32_len_prefixed_bytes(p, n, off0 + 4, &next);
      auto obj = std::make_shared<DataPoint>();
      obj->a = a;
      obj->b = std::move(b);
      return obj;
    }
  };

  nb::class_<DataPoint, pymergetic::nb::CppDataObject>(m, "DataPoint")
      .def(nb::init<>())
      .def_rw("a", &DataPoint::a)
      .def_rw("b", &DataPoint::b)
      .def("serialize", &pymergetic::nb::CppDataObject::serialize)
      .def_static("deserialize", &DataPoint::deserialize)
      .def("to_dict", &DataPoint::to_dict)
      .def("__repr__", &DataPoint::repr);

  m.def("make_datapoint", [](std::int32_t a, std::string b) {
    auto dp = std::make_shared<DataPoint>();
    dp->a = a;
    dp->b = std::move(b);
    return dp;
  });

  nb::class_<pymergetic::common::NativePeerInfo>(m, "NativePeerInfo")
      .def(nb::init<>())
      .def_rw("peer_id", &pymergetic::common::NativePeerInfo::peer_id)
      .def_rw("addresses", &pymergetic::common::NativePeerInfo::addresses);

  nb::class_<pymergetic::common::NativeOptional>(m, "NativeOptional")
      .def(nb::init<>())
      .def_rw("name", &pymergetic::common::NativeOptional::name);

  nb::class_<pymergetic::common::NativeAddress>(m, "NativeAddress")
      .def(nb::init<>())
      .def_rw("ip", &pymergetic::common::NativeAddress::ip);

  nb::class_<pymergetic::common::NativeAddressVecView>(m, "NativeAddressVecView")
      .def("__len__", [](const pymergetic::common::NativeAddressVecView& v) { return v.size(); })
      .def(
          "__getitem__",
          [](pymergetic::common::NativeAddressVecView& v, std::size_t i) -> pymergetic::common::NativeAddress& {
            return v.at(i);
          },
          nb::rv_policy::reference_internal)
      .def("__setitem__", [](pymergetic::common::NativeAddressVecView& v, std::size_t i, pymergetic::common::NativeAddress a) {
        v.set(i, std::move(a));
      })
      .def("append", [](pymergetic::common::NativeAddressVecView& v, pymergetic::common::NativeAddress a) {
        v.append(std::move(a));
      })
      .def("erase", [](pymergetic::common::NativeAddressVecView& v, std::size_t i) { v.erase(i); })
      .def("clear", [](pymergetic::common::NativeAddressVecView& v) { v.clear(); });

  nb::class_<pymergetic::common::NativePeerNested>(m, "NativePeerNested")
      .def(nb::init<>())
      .def_rw("peer_id", &pymergetic::common::NativePeerNested::peer_id)
      .def_rw("main_address", &pymergetic::common::NativePeerNested::main_address)
      .def_ro("addresses", &pymergetic::common::NativePeerNested::addresses, nb::rv_policy::reference_internal);

  m.def("make_native_peer_nested", []() {
    pymergetic::common::NativePeerNested p;
    p.peer_id = "QmHash";
    p.main_address.ip = "127.0.0.1";
    p.addresses.append(pymergetic::common::NativeAddress{.ip = "10.0.0.1"});
    p.addresses.append(pymergetic::common::NativeAddress{.ip = "10.0.0.2"});
    return p;
  });

  nb::class_<pymergetic::common::PacketPayload>(m, "PacketPayload")
      .def(nb::init<>())
      .def("size", [](const pymergetic::common::PacketPayload& p) { return p.data.size(); });

  nb::class_<pymergetic::common::NetworkPacket>(m, "NetworkPacket")
      .def(nb::init<>())
      .def_rw("id", &pymergetic::common::NetworkPacket::id)
      .def_rw("timestamp", &pymergetic::common::NetworkPacket::timestamp)
      .def_rw("payload", &pymergetic::common::NetworkPacket::payload);

  m.def("make_network_packet", []() {
    pymergetic::common::NetworkPacket p;
    p.id = "pkt-1";
    p.timestamp = 1.0;
    auto payload = std::make_shared<pymergetic::common::PacketPayload>();
    payload->data.resize(1024);
    p.payload = std::move(payload);
    return p;
  });
}


