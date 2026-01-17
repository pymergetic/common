#pragma once

#include <nanobind/nanobind.h>

#include <pymergetic/nb/base.hpp>

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
class CppDataObject : public CppObject {
public:
  ~CppDataObject() override = default;

  /// Deterministic binary serialization (round-trip safe).
  virtual ::nanobind::bytes serialize() const = 0;
};

}  // namespace pymergetic::nb


