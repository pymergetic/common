from __future__ import annotations

from dataclasses import dataclass


PMDG_MAGIC = b"PMDG"
PMDG_HEADER_LEN = 16
PMDG_HEADER_VERSION = 1


def fnv1a32(s: str) -> int:
    """FNV-1a 32-bit hash (matches C++ codec.hpp)."""
    h = 2166136261
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def type_id(fully_qualified_name: str) -> int:
    """Stable u32 type id for a fully qualified name (matches C++ codec.hpp)."""
    return fnv1a32(fully_qualified_name)


@dataclass(frozen=True, slots=True)
class Header:
    version: int
    flags: int
    schema_ver: int
    type_id: int
    payload_len: int
    payload_off: int = PMDG_HEADER_LEN


def read_header(blob: bytes) -> Header:
    """Parse and validate the PMDG header from a full message buffer."""
    if len(blob) < PMDG_HEADER_LEN:
        raise ValueError("codec: buffer too small for header")
    if blob[:4] != PMDG_MAGIC:
        raise ValueError("codec: bad magic")

    version = blob[4]
    flags = blob[5]
    schema_ver = int.from_bytes(blob[6:8], "little", signed=False)
    if version != PMDG_HEADER_VERSION:
        raise ValueError("codec: unsupported header version")

    tid = int.from_bytes(blob[8:12], "little", signed=False)
    payload_len = int.from_bytes(blob[12:16], "little", signed=False)

    expected_n = PMDG_HEADER_LEN + payload_len
    if len(blob) != expected_n:
        raise ValueError("codec: payload length mismatch")

    return Header(
        version=version,
        flags=flags,
        schema_ver=schema_ver,
        type_id=tid,
        payload_len=payload_len,
    )


__all__ = [
    "PMDG_MAGIC",
    "PMDG_HEADER_LEN",
    "PMDG_HEADER_VERSION",
    "Header",
    "fnv1a32",
    "type_id",
    "read_header",
]


