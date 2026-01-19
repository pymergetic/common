#pragma once

#include <stdexcept>
#include <string>

namespace pymergetic::common {

/// Base error for codec/serialization failures.
class CodecError : public std::runtime_error {
public:
  using std::runtime_error::runtime_error;
};

/// Thrown when a buffer ends before the requested bytes are available.
class EndOfStreamError : public CodecError {
public:
  using CodecError::CodecError;
};

/// Thrown when the PMDG magic does not match.
class MagicMismatchError : public CodecError {
public:
  using CodecError::CodecError;
};

}  // namespace pymergetic::common


