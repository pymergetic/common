from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile

import pytest


async def _echo_pmdg_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            hdr = await reader.readexactly(16)
            # payload_len is u32 little-endian at offset 12
            payload_len = int.from_bytes(hdr[12:16], "little", signed=False)
            payload = await reader.readexactly(payload_len)
            writer.write(hdr + payload)
            await writer.drain()
    except asyncio.IncompleteReadError:
        # client closed
        return
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()


@pytest.mark.asyncio
async def test_net_uds_pmdg_channel_roundtrip() -> None:
    net = pytest.importorskip("pymergetic.common.net", exc_type=ImportError)

    with tempfile.TemporaryDirectory() as td:
        sock_path = os.path.join(td, "echo.sock")

        server = await asyncio.start_unix_server(_echo_pmdg_server, path=sock_path)
        async with server:
            dialer = net.UdsDialer()
            stream = await asyncio.wait_for(dialer.connect_async(sock_path), timeout=2.0)
            try:
                info = stream.peer_info()
                assert info.transport == net.TransportKind.Uds

                ch = net.PmdgChannel(stream)

                payload = b"hello"
                await asyncio.wait_for(ch.send_async(type_id=123, payload=payload, flags=0, schema_ver=0), timeout=2.0)
                f = await asyncio.wait_for(ch.recv_async(), timeout=2.0)

                assert f.type_id == 123
                assert bytes(f.payload) == payload
            finally:
                # Ensure native socket is closed even if the test fails.
                stream.close()


