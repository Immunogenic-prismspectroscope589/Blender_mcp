"""
Unit tests for wire protocol (4-byte length-prefix JSON over TCP).

No bpy required — pure Python socket-level tests.
"""

from __future__ import annotations

import json
import struct
import socket
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

sys.modules.setdefault("bpy", MagicMock())
sys.modules.setdefault("mathutils", MagicMock())

from blender_mcp.core.protocol import send_message, recv_message, _recv_n


# ---------------------------------------------------------------------------
# _recv_n helper tests
# ---------------------------------------------------------------------------


class TestRecvN:
    def test_recv_exact_bytes(self) -> None:
        """_recv_n returns exactly n bytes when available."""
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [b"abcde"]
        result = _recv_n(sock, 5)
        assert result == b"abcde"

    def test_recv_n_multiple_chunks(self) -> None:
        """_recv_n reassembles data arriving in multiple chunks."""
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [b"ab", b"cd", b"e"]
        result = _recv_n(sock, 5)
        assert result == b"abcde"

    def test_recv_n_returns_none_on_empty(self) -> None:
        """_recv_n returns None when connection is closed (empty recv)."""
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = b""
        result = _recv_n(sock, 4)
        assert result is None

    def test_recv_n_zero_bytes(self) -> None:
        """_recv_n with n=0 returns empty bytes without calling recv."""
        sock = MagicMock(spec=socket.socket)
        result = _recv_n(sock, 0)
        assert result == b""
        sock.recv.assert_not_called()

    def test_recv_n_partial_then_close(self) -> None:
        """_recv_n returns None if connection closes mid-stream."""
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [b"ab", b""]
        result = _recv_n(sock, 5)
        assert result is None


# ---------------------------------------------------------------------------
# send_message tests
# ---------------------------------------------------------------------------


class TestSendMessage:
    def test_send_simple_dict(self) -> None:
        """send_message sends 4-byte BE header + JSON body."""
        sock = MagicMock(spec=socket.socket)
        data = {"tool": "test", "params": {"action": "DO"}}
        result = send_message(sock, data)
        assert result is True
        assert sock.sendall.call_count == 1

        sent_bytes = sock.sendall.call_args[0][0]
        # First 4 bytes = length prefix
        length = struct.unpack(">I", sent_bytes[:4])[0]
        body = sent_bytes[4:]
        assert len(body) == length
        parsed = json.loads(body.decode("utf-8"))
        assert parsed["tool"] == "test"
        assert parsed["params"]["action"] == "DO"

    def test_send_empty_dict(self) -> None:
        """send_message handles empty dict."""
        sock = MagicMock(spec=socket.socket)
        result = send_message(sock, {})
        assert result is True

        sent_bytes = sock.sendall.call_args[0][0]
        length = struct.unpack(">I", sent_bytes[:4])[0]
        body = json.loads(sent_bytes[4:].decode("utf-8"))
        assert body == {}
        assert length == 2  # "{}" is 2 bytes

    def test_send_unicode_data(self) -> None:
        """send_message handles Unicode characters."""
        sock = MagicMock(spec=socket.socket)
        data = {"name": "Kamera", "desc": "Sahne"}
        send_message(sock, data)

        sent_bytes = sock.sendall.call_args[0][0]
        length = struct.unpack(">I", sent_bytes[:4])[0]
        body = sent_bytes[4:]
        assert len(body) == length
        parsed = json.loads(body.decode("utf-8"))
        assert parsed["desc"] == "Sahne"

    def test_send_raises_on_socket_error(self) -> None:
        """send_message propagates socket errors."""
        sock = MagicMock(spec=socket.socket)
        sock.sendall.side_effect = OSError("connection reset")
        try:
            send_message(sock, {"x": 1})
            assert False, "Should have raised"
        except OSError as exc:
            assert "connection reset" in str(exc)

    def test_send_large_payload(self) -> None:
        """send_message handles payloads larger than typical MTU."""
        sock = MagicMock(spec=socket.socket)
        data = {"big": "x" * 100_000}
        result = send_message(sock, data)
        assert result is True

        sent_bytes = sock.sendall.call_args[0][0]
        length = struct.unpack(">I", sent_bytes[:4])[0]
        assert length > 100_000


# ---------------------------------------------------------------------------
# recv_message tests
# ---------------------------------------------------------------------------


class TestRecvMessage:
    def _make_wire_bytes(self, data: dict) -> bytes:
        """Helper: create wire-format bytes from dict."""
        body = json.dumps(data).encode("utf-8")
        return struct.pack(">I", len(body)) + body

    def test_recv_simple_message(self) -> None:
        """recv_message correctly parses a length-prefixed JSON message."""
        data = {"tool": "test", "result": 42}
        wire = self._make_wire_bytes(data)

        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [wire[:4], wire[4:]]

        result = recv_message(sock)
        assert result is not None
        assert result["tool"] == "test"
        assert result["result"] == 42

    def test_recv_returns_none_on_closed_connection(self) -> None:
        """recv_message returns None when header read gets empty bytes."""
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = b""
        result = recv_message(sock)
        assert result is None

    def test_recv_returns_none_on_body_close(self) -> None:
        """recv_message returns None when body read gets empty bytes."""
        body = json.dumps({"x": 1}).encode("utf-8")
        header = struct.pack(">I", len(body))

        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [header, b""]  # header OK, body closed

        result = recv_message(sock)
        assert result is None

    def test_recv_raises_on_timeout(self) -> None:
        """recv_message propagates socket.timeout."""
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = socket.timeout("timed out")

        try:
            recv_message(sock)
            assert False, "Should have raised socket.timeout"
        except socket.timeout:
            pass

    def test_recv_returns_none_on_invalid_json(self) -> None:
        """recv_message returns None for malformed JSON body."""
        bad_body = b"not-json{{"
        header = struct.pack(">I", len(bad_body))

        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [header, bad_body]

        result = recv_message(sock)
        assert result is None


# ---------------------------------------------------------------------------
# Round-trip test
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_send_recv_roundtrip(self) -> None:
        """Data sent via send_message can be reconstructed by recv_message."""
        original = {"tool": "manage_scene", "params": {"action": "LIST"}, "id": 123}
        body = json.dumps(original).encode("utf-8")
        wire = struct.pack(">I", len(body)) + body

        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [wire[:4], wire[4:]]

        result = recv_message(sock)
        assert result == original
