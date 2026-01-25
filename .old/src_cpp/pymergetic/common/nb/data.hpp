#pragma once

#include <nanobind/nanobind.h>

#include <pymergetic/common/objects/__init__.hpp>
#include <pymergetic/common/nb/base.hpp>

namespace pymergetic::nb {

/// Pure data object contract (idempotently recoverable).
///
/// This is NOT a runtime handle. Implementations MUST:
/// - be free of external resources (no sockets, file descriptors, threads, etc.)
/// - be safely copyable/movable (value semantics)
/// - serialize deterministically and be recoverable via a corresponding
///   `deserialize(bytes)` factory at the concrete type.
///
/// NOTE: `deserialize` cannot be virtual+static in C++, so it is enforced by
/// convention at the binding surface (each concrete type exposes a staticmethod).
class CppDataObject : public CppObject, public pymergetic::common::PureDataObject {
public:
  ~CppDataObject() override = default;

  /// Binding-layer serialization adapter.
  /// Concrete types implement `serialize_bytes()` (pure C++).
  ::nanobind::bytes serialize() const {
    const std::string bytes = serialize_bytes();
    return ::nanobind::bytes(bytes.data(), bytes.size());
  }
};

}  // namespace pymergetic::nb


