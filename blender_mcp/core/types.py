"""
Core Type Definitions and Protocols.
Part of the 4-Layer Quality Architecture (L1: Strict Core).
"""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Use typing.TypedDict for Python < 3.12 compatibility
from typing import TypedDict


# ============================================================================
# REGISTRY PROTOCOLS
# ============================================================================


@runtime_checkable
class HandlerProtocol(Protocol):
    """Protocol for all command handlers."""

    def __call__(self, action: str, **params: Any) -> Dict[str, Any]:
        """
        All handlers must accept an action and arbitrary keyword arguments,
        and return a dictionary response.
        """
        ...

    _handler_schema: Dict[str, Any]


class HandlerMetadata(TypedDict):
    """Metadata for registered handlers."""

    name: str
    description: str
    actions: List[str]
    schema: Dict[str, Any]
    signature: str
    module: str
    category: str
    priority: int


# ============================================================================
# EXECUTION PROTOCOLS
# ============================================================================


@runtime_checkable
class ExecutionResultProtocol(Protocol):
    """Protocol for ExecutionResult dataclass."""

    success: bool
    result: Optional[Any]
    error: Optional[str]
    error_code: Optional[str]
    alternatives: Optional[List[str]]

    def to_dict(self) -> Dict[str, Any]: ...
    def to_error_dict(self) -> Dict[str, Any]: ...


# ============================================================================
# INTEGRATION PROTOCOLS
# ============================================================================


class ToolInfo(TypedDict):
    """Tool information for catalog."""

    name: str
    description: str
    category: str
    actions: List[str]
    schema: Dict[str, Any]


class SketchfabGltf(TypedDict):
    """GLTF download info from Sketchfab."""

    url: str
    size: int
    expires: int


class SketchfabDownloadData(TypedDict):
    """Data payload for Sketchfab download endpoint."""

    gltf: SketchfabGltf
    usdz: Optional[Dict[str, Any]]


class SketchfabModel(TypedDict):
    """Simplified Sketchfab model info."""

    uid: str
    name: str
    viewCount: int
    likeCount: int
    vertexCount: int
    faceCount: int


class SketchfabSearchResponse(TypedDict):
    """Response from Sketchfab search API."""

    results: List[SketchfabModel]
    next: Optional[str]
    previous: Optional[str]
