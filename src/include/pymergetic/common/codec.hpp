#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace pymergetic::common::codec {

inline void append_u8(std::string& out, std::uint8_t v) { out.push_back(static_cast<char>(v)); }

inline void append_u32_le(std::string& out, std::uint32_t v) {
  out.push_back(static_cast<char>(v & 0xFF));
  out.push_back(static_cast<char>((v >> 8) & 0xFF));
  out.push_back(static_cast<char>((v >> 16) & 0xFF));
  out.push_back(static_cast<char>((v >> 24) & 0xFF));
}

inline void append_i32_le(std::string& out, std::int32_t v) {
  append_u32_le(out, static_cast<std::uint32_t>(v));
}

inline std::uint32_t read_u32_le(const char* p, std::size_t n, std::size_t off) {
  if (off + 4 > n) {
    throw std::runtime_error("codec: read_u32_le out of bounds");
  }
  return (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off])) |
          (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off + 1])) << 8) |
          (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off + 2])) << 16) |
          (static_cast<std::uint32_t>(static_cast<unsigned char>(p[off + 3])) << 24));
}

inline std::int32_t read_i32_le(const char* p, std::size_t n, std::size_t off) {
  return static_cast<std::int32_t>(read_u32_le(p, n, off));
}

inline void append_u32_len_prefixed(std::string& out, const std::string& bytes) {
  append_u32_le(out, static_cast<std::uint32_t>(bytes.size()));
  out.append(bytes);
}

inline std::string read_u32_len_prefixed_bytes(const char* p, std::size_t n, std::size_t off, std::size_t* next_off) {
  const std::uint32_t len = read_u32_le(p, n, off);
  const std::size_t start = off + 4;
  const std::size_t end = start + static_cast<std::size_t>(len);
  if (end > n) {
    throw std::runtime_error("codec: length-prefixed read out of bounds");
  }
  if (next_off) {
    *next_off = end;
  }
  return std::string(p + start, p + end);
}

}  // namespace pymergetic::common::codec


