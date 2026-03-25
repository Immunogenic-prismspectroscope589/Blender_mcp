import json
import socket
import struct
import logging
from typing import Dict, Any, Optional, cast

logger = logging.getLogger(__name__)


def send_message(sock: socket.socket, data: Dict[str, Any]) -> bool:
    """
    Send a message with a 4-byte Big Endian length prefix.

    Args:
        sock (socket.socket): The connected socket.
        data (dict): The JSON-serializable dictionary to send.

    Raises:
        ValueError: If data is not serializable.
        socket.error: If sending fails.
    """
    try:
        json_bytes = json.dumps(data).encode("utf-8")
        # 4-byte Length Prefix (Big Endian)
        length_prefix = struct.pack(">I", len(json_bytes))

        # Send all (Prefix + Body)
        sock.sendall(length_prefix + json_bytes)
        return True
    except Exception as e:
        logger.error(f"[Protocol] Send Error: {e}")
        raise e


def recv_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Receive a message with a 4-byte Big Endian length prefix.
    Blocks until a full message is received or connection is closed.

    Args:
        sock (socket.socket): The connected socket.

    Returns:
        dict: The parsed JSON message.
        None: If connection is closed or header is invalid.
    """
    try:
        # 1. Read 4-byte Header
        raw_len = _recv_n(sock, 4)
        if not raw_len:
            return None  # Connection closed cleanly

        msg_len = struct.unpack(">I", raw_len)[0]

        # 2. Read Body
        msg_bytes = _recv_n(sock, msg_len)
        if not msg_bytes:
            return None  # Connection broken mid-message

        return cast(Dict[str, Any], json.loads(msg_bytes.decode("utf-8")))

    except socket.timeout:
        # Caller should handle timeout
        raise
    except Exception as e:
        logger.error(f"[Protocol] Read Error: {e}")
        return None


def _recv_n(sock: socket.socket, n: int) -> Optional[bytes]:
    """Helper to receive exactly n bytes."""
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data
