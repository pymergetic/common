#pragma once

#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>

namespace pymergetic::common::codec {

// Canonical binary header for CppDataObject payloads.
//
// Layout (all little-endian):
//   magic[4]      = "PMDG"
//   u8  version   = 1
//   u32 type_id   = stable type id for the concrete data object
//   u32 len       = payload length in bytes
//   payload[len]
//
// This makes payloads self-describing and forward-compatible.
inline constexpr char k_magic[4] = {'P', 'M', 'D', 'G'};
inline constexpr std::uint8_t k_header_version = 1;

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

struct Header {
  std::uint8_t version{};
  std::uint32_t type_id{};
  std::uint32_t payload_len{};
  std::size_t payload_off{};
};

inline void append_header(std::string& out, std::uint32_t type_id, std::uint32_t payload_len) {
  out.append(k_magic, k_magic + 4);
  append_u8(out, k_header_version);
  append_u32_le(out, type_id);
  append_u32_le(out, payload_len);
}

inline Header read_header(const char* p, std::size_t n) {
  if (n < 4 + 1 + 4 + 4) {
    throw std::runtime_error("codec: buffer too small for header");
  }
  if (p[0] != k_magic[0] || p[1] != k_magic[1] || p[2] != k_magic[2] || p[3] != k_magic[3]) {
    throw std::runtime_error("codec: bad magic");
  }
  Header h;
  h.version = static_cast<std::uint8_t>(p[4]);
  if (h.version != k_header_version) {
    throw std::runtime_error("codec: unsupported header version");
  }
  h.type_id = read_u32_le(p, n, 5);
  h.payload_len = read_u32_le(p, n, 9);
  h.payload_off = 13;
  if (h.payload_off + static_cast<std::size_t>(h.payload_len) != n) {
    throw std::runtime_error("codec: payload length mismatch");
  }
  return h;
}

}  // namespace pymergetic::common::codec


