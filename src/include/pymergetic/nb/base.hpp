#pragma once

#include <nanobind/nanobind.h>
#include <string>

namespace pymergetic::nb {

/// Binding-layer base class for native objects exposed to Python.
///
/// IMPORTANT:
/// - This is a Level-2 (bindings) concept (it depends on nanobind).
/// - Do not use this in Level-1 engine code (EP-0006: Level 1 must not depend on Python).
class CppObject {
public:
  virtual ~CppObject() = default;

  /// Debug representation.
  virtual std::string repr() const { return "<CppObject>"; }

  /// Fast serialization to a Python dict (zero extra Python-side validation/ORM work).
  virtual ::nanobind::dict to_dict() const { return ::nanobind::dict(); }
};

}  // namespace pymergetic::nb


