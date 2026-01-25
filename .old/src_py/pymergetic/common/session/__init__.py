from __future__ import annotations

import importlib

try:
    _ni = importlib.import_module("pymergetic.common.__cpp__")  # type: ignore
except Exception as e:  # pragma: no cover
    raise ImportError(
        "pymergetic-common native module is required. "
        "Build/install a wheel with the compiled extension and ensure "
        "`pymergetic.common.__cpp__` is importable."
    ) from e

AuthPolicy = _ni.AuthPolicy
SessionContext = _ni.SessionContext
apply_policy = _ni.apply_policy
make_session = _ni.make_session


class SessionStream:
    def __init__(self, stream, session: SessionContext) -> None:
        self._stream = stream
        self._session = session

    @property
    def session(self) -> SessionContext:
        return self._session

    @property
    def stream(self):
        return self._stream

    def peer_info(self):
        return self._stream.peer_info()

    def read_exact_async(self, nbytes: int):
        return self._stream.read_exact_async(nbytes)

    def write_async(self, data: bytes):
        return self._stream.write_async(data)

    def close(self) -> None:
        return self._stream.close()


def make_session_stream(stream, policy: AuthPolicy, session_id: str = "") -> SessionStream:
    ctx = make_session(stream.peer_info(), policy, session_id)
    return SessionStream(stream, ctx)

__all__ = [
    "AuthPolicy",
    "SessionContext",
    "SessionStream",
    "apply_policy",
    "make_session",
    "make_session_stream",
]

