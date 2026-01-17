#pragma once

#include <string>

namespace pymergetic::common {

// Minimal shared definitions to anchor ABI expectations across extensions.
// Extend carefully: prefer additive changes.

using PeerId = std::string;

}  // namespace pymergetic::common


