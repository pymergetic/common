#pragma once

#include <cstdint>
#include <string>

namespace pymergetic::common::net {

/// Transport kind (L4).
enum class TransportKind : std::uint8_t {
  Unknown = 0,
  Uds = 1,
  Tcp = 2,
  Libp2pStream = 3,
};

/// Authentication kind (L5-ish / session identity binding), produced by the transport stack.
enum class AuthKind : std::uint8_t {
  None = 0,
  UdsPeerCred = 1,
  TlsMtls = 2,
  Libp2pSecure = 3,
  Psk = 4,
};

/// Canonical connection / peer information.
///
/// This is intended primarily for:
/// - logging / tracing / observability
/// - stable identity inputs for L7 authZ and routing decisions
///
/// It is *not* a policy object.
struct PeerInfo {
  TransportKind transport = TransportKind::Unknown;
  AuthKind auth_kind = AuthKind::None;
  bool authenticated = false;

  // Canonical identity string (stable across transports).
  // Examples: "uid:1000", "tls:sha256:<fp>", "p2p:<peerid>".
  std::string peer_id;

  // Human-friendly, optional.
  std::string peer_name;

  // Optional addressing/debug info.
  // Examples: "unix:/path", "tcp:host:port", "libp2p:<multiaddr>".
  std::string local;
  std::string remote;

  // Optional evidence (keep small; prefer fingerprints/ids).
  std::string cert_fingerprint;  // e.g. sha256 hex
  std::string cert_pem;          // optional (may be large)
  std::string pubkey;            // optional (public key only)
  std::string psk_id;            // optional (NEVER store the secret)

  // OS identity evidence (for UDS; -1 means “unknown / not available”).
  std::int32_t peer_pid = -1;
  std::int32_t peer_uid = -1;
  std::int32_t peer_gid = -1;
};

}  // namespace pymergetic::common::net


