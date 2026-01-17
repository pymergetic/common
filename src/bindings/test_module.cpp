#include <nanobind/nanobind.h>
#include <nanobind/stl/optional.h>
#include <nanobind/stl/shared_ptr.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/vector.h>

#include <pymergetic/nb/base.hpp>
#include <pymergetic/nb/data.hpp>

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

  m.def("add", [](int a, int b) { return a + b; });

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

    nb::bytes serialize() const override {
      // Format: [u8 version=1][i32 little][u32 len][bytes]
      std::string out;
      out.push_back(static_cast<char>(1));
      auto put_u32 = [&](std::uint32_t v) {
        out.push_back(static_cast<char>(v & 0xFF));
        out.push_back(static_cast<char>((v >> 8) & 0xFF));
        out.push_back(static_cast<char>((v >> 16) & 0xFF));
        out.push_back(static_cast<char>((v >> 24) & 0xFF));
      };
      auto put_i32 = [&](std::int32_t v) { put_u32(static_cast<std::uint32_t>(v)); };
      put_i32(a);
      put_u32(static_cast<std::uint32_t>(b.size()));
      out.append(b);
      return nb::bytes(out.data(), out.size());
    }

    static std::shared_ptr<DataPoint> deserialize(nb::bytes data) {
      const char* p = data.c_str();
      const std::size_t n = data.size();
      if (n < 1 + 4 + 4) {
        throw std::runtime_error("DataPoint: buffer too small");
      }
      const std::uint8_t ver = static_cast<std::uint8_t>(p[0]);
      if (ver != 1) {
        throw std::runtime_error("DataPoint: unsupported version");
      }
      auto get_u32 = [&](std::size_t off) -> std::uint32_t {
        return (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off])) |
                (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off + 1])) << 8) |
                (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off + 2])) << 16) |
                (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off + 3])) << 24));
      };
      const std::int32_t a = static_cast<std::int32_t>(get_u32(1));
      const std::uint32_t len = get_u32(1 + 4);
      if (n < 1 + 4 + 4 + len) {
        throw std::runtime_error("DataPoint: invalid length");
      }
      auto obj = std::make_shared<DataPoint>();
      obj->a = a;
      obj->b.assign(p + (1 + 4 + 4), p + (1 + 4 + 4 + len));
      return obj;
    }
  };

  nb::class_<DataPoint, pymergetic::nb::CppDataObject>(m, "DataPoint")
      .def(nb::init<>())
      .def_rw("a", &DataPoint::a)
      .def_rw("b", &DataPoint::b)
      .def("serialize", &DataPoint::serialize)
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


