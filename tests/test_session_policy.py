from __future__ import annotations

import os

from pymergetic.common.net.peer_info import PeerInfo
from pymergetic.common.session import AuthPolicy, SessionStream, apply_policy, make_session, make_session_stream


def test_apply_policy_anonymous() -> None:
    peer = PeerInfo()
    policy = AuthPolicy()
    policy.allow_anonymous = True

    ctx = apply_policy(peer, policy)
    assert ctx.accepted is True
    assert ctx.authenticated is False


def test_apply_policy_allow_uid() -> None:
    peer = PeerInfo()
    uid = os.getuid() if hasattr(os, "getuid") else 1000
    peer.peer_uid = uid

    policy = AuthPolicy()
    policy.allow_uid(uid)

    ctx = apply_policy(peer, policy)
    assert ctx.accepted is True
    assert ctx.authenticated is True
    assert ctx.principal == f"uid:{uid}"


def test_apply_policy_requires_transport_auth() -> None:
    peer = PeerInfo()

    policy = AuthPolicy()
    policy.allow_anonymous = True
    policy.require_transport_authenticated = True

    ctx = apply_policy(peer, policy)
    assert ctx.accepted is False
    assert ctx.authenticated is False


def test_make_session_generates_id() -> None:
    peer = PeerInfo()
    policy = AuthPolicy()
    policy.allow_anonymous = True

    ctx = make_session(peer, policy)
    assert ctx.session_id


def test_make_session_stream_wraps() -> None:
    class DummyStream:
        def __init__(self, peer: PeerInfo) -> None:
            self._peer = peer

        def peer_info(self) -> PeerInfo:
            return self._peer

        def read_exact_async(self, nbytes: int):
            return ("read", nbytes)

        def write_async(self, data: bytes):
            return ("write", data)

        def close(self) -> None:
            return None

    peer = PeerInfo()
    policy = AuthPolicy()
    policy.allow_anonymous = True
    stream = DummyStream(peer)

    sstream = make_session_stream(stream, policy)
    assert isinstance(sstream, SessionStream)
    assert sstream.session.session_id
    assert sstream.peer_info() is peer
    assert sstream.read_exact_async(4) == ("read", 4)
    assert sstream.write_async(b"hi") == ("write", b"hi")
