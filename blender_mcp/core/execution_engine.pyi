from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    alternatives: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]: ...
    def to_error_dict(self) -> Dict[str, Any]: ...

class ExecutionEngine:
    MODAL_OPERATORS: set[str]
    UI_DEPENDENT_OPERATORS: set[str]
    SCENE_DESTRUCTIVE_OPERATORS: set[str]
    DANGEROUS_OPERATORS: set[str]
    OPERATOR_ALTERNATIVES: Dict[str, List[str]]

    @classmethod
    def check_poll(cls, operator_path: str) -> Tuple[bool, Optional[str]]: ...
    @classmethod
    def execute(
        cls,
        operator_path: str,
        params: Optional[Dict[str, Any]] = None,
        context_override: Optional[Dict[str, Any]] = None,
        exec_context: Optional[str] = None,
        allow_dangerous: bool = False,
        check_context: bool = True,
    ) -> ExecutionResult: ...
    @classmethod
    def execute_safe(cls, operator_path: str, **params: Any) -> ExecutionResult: ...
    @classmethod
    def execute_batch(
        cls, operations: List[Tuple[str, Dict[str, Any]]], stop_on_error: bool = True
    ) -> List[ExecutionResult]: ...
    @classmethod
    def is_safe(cls, operator_path: str) -> Tuple[bool, Optional[str]]: ...

# =============================================================================
# OPERATOR STUBS (PARTIAL)
# =============================================================================

class _OpsBase:
    def __getattr__(self, name: str) -> Any: ...

class _ObjectOps(_OpsBase):
    def mode_set(
        self, mode: str = ..., toggle: bool = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def select_all(
        self, action: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def delete(
        self, use_global: bool = ..., confirm: bool = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def duplicate(
        self, linked: bool = ..., mode: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def shade_smooth(self, _exec_context: str = ..., **kwargs: Any) -> ExecutionResult: ...
    def shade_flat(self, _exec_context: str = ..., **kwargs: Any) -> ExecutionResult: ...
    def origin_set(
        self, type: str = ..., center: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def modifier_add(
        self, type: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def modifier_apply(
        self, modifier: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...

class _MeshOps(_OpsBase):
    def primitive_cube_add(
        self,
        size: float = ...,
        location: Tuple[float, float, float] = ...,
        rotation: Tuple[float, float, float] = ...,
        scale: Tuple[float, float, float] = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def primitive_plane_add(
        self,
        size: float = ...,
        location: Tuple[float, float, float] = ...,
        rotation: Tuple[float, float, float] = ...,
        scale: Tuple[float, float, float] = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def primitive_uv_sphere_add(
        self,
        radius: float = ...,
        location: Tuple[float, float, float] = ...,
        rotation: Tuple[float, float, float] = ...,
        scale: Tuple[float, float, float] = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def primitive_cylinder_add(
        self,
        radius: float = ...,
        depth: float = ...,
        location: Tuple[float, float, float] = ...,
        rotation: Tuple[float, float, float] = ...,
        scale: Tuple[float, float, float] = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def subdivide(
        self,
        number_cuts: int = ...,
        smoothness: float = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def extrude_region_move(
        self,
        TRANSFORM_OT_translate: Optional[Dict[str, Any]] = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def select_all(
        self, action: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...

class _WmOps(_OpsBase):
    def save_mainfile(
        self,
        filepath: str = ...,
        check_existing: bool = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def open_mainfile(
        self, filepath: str = ..., _exec_context: str = ..., **kwargs: Any
    ) -> ExecutionResult: ...
    def quit_blender(self, _exec_context: str = ..., **kwargs: Any) -> ExecutionResult: ...

class _RenderOps(_OpsBase):
    def render(
        self,
        animation: bool = ...,
        write_still: bool = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...
    def opengl(
        self,
        animation: bool = ...,
        write_still: bool = ...,
        view_context: bool = ...,
        _exec_context: str = ...,
        **kwargs: Any,
    ) -> ExecutionResult: ...

class SafeOps:
    @property
    def object(self) -> _ObjectOps: ...
    @property
    def mesh(self) -> _MeshOps: ...
    @property
    def wm(self) -> _WmOps: ...
    @property
    def render(self) -> _RenderOps: ...
    def __getattr__(self, name: str) -> Any: ...

safe_ops: SafeOps

def safe_execute(
    operator_path: Optional[str] = None,
    fallback_result: Optional[Dict[str, Any]] = None,
    allow_dangerous: bool = False,
) -> Any: ...
def require_context(require_scene: bool = True, require_object: bool = False) -> Any: ...
def safe_mode_set(mode: str, obj: Optional[Any] = None) -> ExecutionResult: ...
def safe_delete(objects: List[Any], use_global: bool = False) -> ExecutionResult: ...
