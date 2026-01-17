#pragma once

namespace pymergetic::common {

// Placeholder for future C++ registration base types.
// (Keep stable; used as an ABI anchor across pymergetic extensions.)

struct RegistryBase {
  virtual ~RegistryBase() = default;
};

}  // namespace pymergetic::common


