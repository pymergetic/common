#pragma once

#include <string>

namespace pymergetic::common {

/// Pure C++ data object contract (Level 1 / Python-free).
///
/// Implementations MUST:
/// - be free of external resources (no sockets, file descriptors, threads, etc.)
/// - be safely copyable/movable (value semantics)
/// - serialize deterministically (idempotent roundtrip)
///
/// NOTE: `deserialize` cannot be expressed as a virtual static function in C++.
/// Each concrete type should expose a corresponding factory by convention.
class PureDataObject {
public:
  virtual ~PureDataObject() = default;

  /// Deterministic binary serialization (round-trip safe).
  /// Returned bytes may contain nulls; treat as binary, not text.
  virtual std::string serialize_bytes() const = 0;
};

}  // namespace pymergetic::common


