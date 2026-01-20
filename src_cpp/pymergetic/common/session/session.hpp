#pragma once

#include <pymergetic/common/net/peer_info.hpp>

#include <cstdint>
#include <map>
#include <iomanip>
#include <random>
#include <set>
#include <sstream>
#include <string>

namespace pymergetic::common::session {

struct AuthPolicy {
  bool allow_anonymous = false;
  bool require_transport_authenticated = false;
  std::set<std::int32_t> allow_uids;
  std::set<std::string> allow_peer_ids;
};

struct SessionContext {
  pymergetic::common::net::PeerInfo peer;
  bool accepted = false;
  bool authenticated = false;
  std::string principal;
  std::string session_id;
  std::map<std::string, std::string> claims;
};

inline SessionContext apply_policy(const pymergetic::common::net::PeerInfo& peer, const AuthPolicy& policy) {
  SessionContext ctx;
  ctx.peer = peer;

  const bool evidence_ok = !policy.require_transport_authenticated || peer.authenticated;
  const bool uid_allowed = peer.peer_uid >= 0 && policy.allow_uids.count(peer.peer_uid) > 0;
  const bool peer_id_allowed = !peer.peer_id.empty() && policy.allow_peer_ids.count(peer.peer_id) > 0;
  const bool allow = policy.allow_anonymous || uid_allowed || peer_id_allowed;

  ctx.accepted = evidence_ok && allow;
  if (ctx.accepted) {
    ctx.authenticated = peer.authenticated || uid_allowed || peer_id_allowed;
    if (ctx.authenticated) {
      if (!peer.peer_id.empty()) {
        ctx.principal = peer.peer_id;
      } else if (peer.peer_uid >= 0) {
        ctx.principal = "uid:" + std::to_string(peer.peer_uid);
      }
    }
  }

  return ctx;
}

inline std::string make_session_id() {
  std::random_device rd;
  std::mt19937_64 gen(rd());
  std::uint64_t a = gen();
  std::uint64_t b = gen();
  std::ostringstream oss;
  oss << std::hex << std::setfill('0') << std::setw(16) << a << std::setw(16) << b;
  return oss.str();
}

inline SessionContext make_session(const pymergetic::common::net::PeerInfo& peer,
                                   const AuthPolicy& policy,
                                   std::string session_id = "") {
  SessionContext ctx = apply_policy(peer, policy);
  if (session_id.empty()) {
    ctx.session_id = make_session_id();
  } else {
    ctx.session_id = std::move(session_id);
  }
  return ctx;
}

}  // namespace pymergetic::common::session

