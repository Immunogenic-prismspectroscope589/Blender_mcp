"""
Event Ledger for Blender MCP 1.0.0
"The Immutable Truth"

Append-only log of all operations, ensuring auditability and replay capability.

High Mode Philosophy:
"If it isn't in the ledger, it didn't happen."
"""

import json
import time
import os
import uuid
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from .logging_config import get_logger

logger = get_logger()


class EventLedger:
    """
    Append-only ledger for MCP operations.
    Persists events to a JSONL file.
    """

    _instance = None
    _initialized: bool = False

    def __new__(cls) -> Any:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, log_dir: Optional[str] = None) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.log_dir = log_dir or os.path.join(os.path.expanduser("~"), ".blender_mcp", "ledger")
        os.makedirs(self.log_dir, exist_ok=True)

        # Session ID for this run
        self.session_id = str(uuid.uuid4())[:8]
        date_str = datetime.now().strftime("%Y-%m-%d")
        self.log_file = os.path.join(self.log_dir, f"ledger_{date_str}_{self.session_id}.jsonl")

        self._initialized = True
        logger.info(f"[Ledger] Initialized at {self.log_file}")

    def log_event(
        self,
        event_type: str,
        tool: str,
        params: Dict[str, Any],
        status: str,
        duration_ms: float,
        state_hash: str = "",
        error: Optional[str] = None,
    ) -> None:
        """
        Append event to ledger.

        Args:
            event_type: "TOOL_CALL", "SYSTEM_EVENT", etc.
            tool: Tool/Handler name
            params: Input parameters (sanitized)
            status: "SUCCESS", "FAILED"
            duration_ms: Execution time
            state_hash: Structural hash of scene (post-execution)
            error: Error message if failed
        """
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "iso_time": datetime.now(timezone.utc).isoformat() + "Z",
            "type": event_type,
            "tool": tool,
            "params": self._sanitize(params),
            "status": status,
            "duration_ms": duration_ms,
            "state_hash": state_hash,
            "error": error,
        }

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            # Fallback logging if disk fails
            logger.error(f"[Ledger] Write Failed: {e}")

    def _sanitize(self, data: Any) -> Any:
        """Sanitize data for JSON serialization."""
        if isinstance(data, dict):
            return {k: self._sanitize(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize(v) for v in data]
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            return str(data)  # Fallback for complex objects


# Global Instance Accessor
_ledger_instance = None


def get_ledger() -> EventLedger:
    global _ledger_instance
    if _ledger_instance is None:
        _ledger_instance = EventLedger()
    return _ledger_instance
