"""
Tool Discovery & Introspection System for Blender MCP 1.0.0

Provides:
- Automatic action discovery from handler source
- Dynamic schema generation
- Usage example generation
- Tool catalog with search capabilities
- Multi-language alias resolution

High Mode Philosophy: Self-documenting, self-discovering systems.
"""

import inspect
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ActionInfo:
    """Information about a handler action."""

    name: str
    description: str = ""
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    related_actions: List[str] = field(default_factory=list)
    category: str = "general"


@dataclass
class ToolInfo:
    """Complete information about a tool."""

    name: str
    description: str
    category: str
    actions: List[ActionInfo]
    schema: Dict[str, Any]
    aliases: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"


class ActionDiscovery:
    """
    Automatic action discovery from handler functions.
    """

    @staticmethod
    def from_source(source_code: str) -> List[str]:
        """
        Extract action names from handler source code.

        Detects patterns like:
        - if action == "ACTION_NAME":
        - elif action == "ACTION_NAME":
        - elif action in ("ACTION1", "ACTION2"):
        """
        actions = []

        # Pattern: if action == "NAME" or elif action == "NAME"
        pattern1 = r'(?:if|elif)\s+action\s*==\s*["\']([^"\']+)["\']'
        matches1 = re.findall(pattern1, source_code)
        actions.extend(matches1)

        # Pattern: elif action in ("NAME1", "NAME2")
        pattern2 = r"(?:if|elif)\s+action\s+in\s*\(([^)]+)\)"
        matches2 = re.findall(pattern2, source_code)
        for match in matches2:
            # Extract individual names from tuple
            names = re.findall(r'["\']([^"\']+)["\']', match)
            actions.extend(names)

        # Pattern: if action in ["NAME1", "NAME2"]
        pattern3 = r"(?:if|elif)\s+action\s+in\s*\[([^\]]+)\]"
        matches3 = re.findall(pattern3, source_code)
        for match in matches3:
            names = re.findall(r'["\']([^"\']+)["\']', match)
            actions.extend(names)

        # Remove duplicates while preserving order
        seen = set()
        unique_actions = []
        for action in actions:
            if action not in seen:
                seen.add(action)
                unique_actions.append(action)

        return unique_actions

    @staticmethod
    def from_function(func: Callable) -> List[str]:
        """Extract actions from a handler function."""
        try:
            source = inspect.getsource(func)
            return ActionDiscovery.from_source(source)
        except (OSError, TypeError):
            # If source not available, try to get from _handler_actions
            return getattr(func, "_handler_actions", [])


class SchemaGenerator:
    """
    Generate JSON schemas from function signatures.
    """

    TYPE_MAP = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    @classmethod
    def from_function(
        cls,
        func: Callable,
        actions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON schema from function signature.

        Args:
            func: Handler function
            actions: List of valid actions

        Returns:
            JSON Schema dictionary
        """
        sig = inspect.signature(func)
        title = func.__name__.replace("manage_", "").replace("_", " ").title()
        description = inspect.getdoc(func) or "No description available."
        properties: Dict[str, Dict[str, Any]] = {}
        required: List[str] = []

        for name, param in sig.parameters.items():
            if name in ("args", "kwargs"):
                continue

            prop: Dict[str, Any] = {}

            # Determine type
            if param.annotation != inspect.Parameter.empty:
                prop["type"] = cls.TYPE_MAP.get(param.annotation, "string")
            elif param.default != inspect.Parameter.empty:
                prop["type"] = cls.TYPE_MAP.get(type(param.default), "string")
            else:
                prop["type"] = "string"

            # Add default if available
            if param.default != inspect.Parameter.empty:
                prop["default"] = param.default

            # Special handling for action parameter
            if name == "action" and actions:
                prop["enum"] = actions
                prop["description"] = "Action to perform"
                required.append("action")
            elif param.default == inspect.Parameter.empty and name != "kwargs":
                required.append(name)

            properties[name] = prop

        return {
            "type": "object",
            "title": title,
            "description": description,
            "properties": properties,
            "required": required,
        }


class ExampleGenerator:
    """
    Generate usage examples for tools and actions.
    """

    # Common example templates
    TEMPLATES = {
        "manage_animation": {
            "INSERT_KEYFRAME": [
                {
                    "description": "Insert location keyframe at current frame",
                    "params": {"action": "INSERT_KEYFRAME", "property_path": "location"},
                },
                {
                    "description": "Insert rotation keyframe on Z axis (accepts rotation_z, rz, dönüş_z, 旋转_z)",
                    "params": {"action": "INSERT_KEYFRAME", "property_path": "rotation_z"},
                },
                {
                    "description": "Insert keyframe at specific frame using Maya-style notation",
                    "params": {"action": "INSERT_KEYFRAME", "property_path": "tx", "frame": 25},
                },
            ],
            "SET_FRAME": [
                {
                    "description": "Jump to frame 100",
                    "params": {"action": "SET_FRAME", "frame": 100},
                }
            ],
        },
        "manage_batch": {
            "RENAME": [
                {
                    "description": "Add prefix to selected objects",
                    "params": {"action": "RENAME", "name_prefix": "Hero_"},
                }
            ],
            "DUPLICATE": [
                {
                    "description": "Create 3 copies with 2-unit X offset",
                    "params": {
                        "action": "DUPLICATE",
                        "duplicate_count": 3,
                        "duplicate_offset": [2, 0, 0],
                    },
                }
            ],
        },
        "manage_scene": {
            "INSPECT_SCENE": [
                {
                    "description": "Get complete scene information",
                    "params": {"action": "INSPECT_SCENE"},
                }
            ]
        },
    }

    @classmethod
    def get_examples(cls, tool_name: str, action: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get usage examples for a tool/action.

        Args:
            tool_name: Tool name (e.g., "manage_animation")
            action: Specific action (optional)

        Returns:
            List of example dictionaries
        """
        tool_examples = cls.TEMPLATES.get(tool_name, {})

        if action:
            return tool_examples.get(action, [])

        # Return all examples for tool
        all_examples = []
        for action_examples in tool_examples.values():
            all_examples.extend(action_examples)
        return all_examples

    @classmethod
    def generate_example(
        cls,
        tool_name: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a single example."""
        base: Dict[str, Any] = {
            "tool": tool_name,
            "action": action,
        }

        if params:
            base["params"] = params

        return base


class ToolCatalog:
    """
    Central registry for tool information with search capabilities.
    """

    _instance = None
    _initialized = False

    def __new__(cls) -> "ToolCatalog":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if ToolCatalog._initialized:
            return

        self.tools: Dict[str, ToolInfo] = {}
        self.action_index: Dict[str, List[str]] = {}  # action -> [tool names]
        self.category_index: Dict[str, List[str]] = {}  # category -> [tool names]

        ToolCatalog._initialized = True

    def register_tool(
        self,
        name: str,
        func: Callable,
        category: str = "general",
        description: str = "",
        actions: Optional[List[str]] = None,
        params_schema: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        Register a tool in the catalog.

        Args:
            name: Tool name
            handler_func: Handler function
            category: Tool category
            actions: List of valid actions
            description: Tool description
        """
        # Auto-discover actions if not provided
        if actions is None:
            actions = ActionDiscovery.from_function(func)

        # Generate schema
        schema = SchemaGenerator.from_function(func, actions)

        # Build action info list
        action_infos = []
        for action in actions:
            info = ActionInfo(
                name=action,
                description=f"Perform {action} operation",
                examples=ExampleGenerator.get_examples(name, action),
            )
            action_infos.append(info)

            # Index action
            if action not in self.action_index:
                self.action_index[action] = []
            self.action_index[action].append(name)

        # Create tool info
        tool_info = ToolInfo(
            name=name,
            description=description or inspect.getdoc(func) or "No description",
            category=category,
            actions=action_infos,
            schema=schema,
            examples=ExampleGenerator.get_examples(name),
        )

        self.tools[name] = tool_info

        # Index category
        if category not in self.category_index:
            self.category_index[category] = []
        self.category_index[category].append(name)

    def get_tool(self, name: str) -> Optional[ToolInfo]:
        """Get tool information by name."""
        return self.tools.get(name)

    def search(self, query: str) -> List[Tuple[str, float]]:
        """
        Search tools by name or action.

        Returns:
            List of (tool_name, relevance_score) tuples
        """
        from .fuzzy_matcher import fuzzy_match

        results = []

        # Search tool names
        tool_names = list(self.tools.keys())
        name_matches = fuzzy_match(query, tool_names, threshold=0.4)
        results.extend(name_matches)

        # Search actions
        for action, tool_names in self.action_index.items():
            if query.lower() in action.lower():
                for tool_name in tool_names:
                    results.append((tool_name, 0.8))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def get_catalog(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete tool catalog.

        Args:
            category: Filter by category (optional)

        Returns:
            Dictionary with tool information
        """
        if category:
            tool_names = self.category_index.get(category, [])
        else:
            tool_names = list(self.tools.keys())

        catalog: Dict[str, Any] = {
            "version": "1.0.0",
            "total_tools": len(tool_names),
            "categories": list(self.category_index.keys()),
            "tools": {},
        }

        for name in tool_names:
            tool = self.tools[name]
            catalog["tools"][name] = {
                "description": tool.description,
                "category": tool.category,
                "actions": [a.name for a in tool.actions],
                "action_count": len(tool.actions),
            }

        return catalog

    def get_action_help(self, tool_name: str, action: str) -> Optional[Dict[str, Any]]:
        """Get detailed help for a specific action."""
        tool = self.tools.get(tool_name)
        if not tool:
            return None

        for action_info in tool.actions:
            if action_info.name == action:
                return {
                    "tool": tool_name,
                    "action": action,
                    "description": action_info.description,
                    "examples": action_info.examples,
                    "related": action_info.related_actions,
                    "schema": tool.schema,
                }

        return None


class MultiLanguageResolver:
    """
    Resolve tool names and actions across multiple languages.
    """

    # Tool name aliases
    TOOL_ALIASES = {
        # English variations
        "animation": "manage_animation",
        "scene": "manage_scene",
        "objects": "manage_objects",
        "modeling": "manage_modeling",
        "materials": "manage_materials",
        "render": "manage_rendering",
        "export": "manage_export",
        "batch": "manage_batch",
        # Turkish
        "animasyon": "manage_animation",
        "sahne": "manage_scene",
        "nesneler": "manage_objects",
        "objeler": "manage_objects",
        "modelleme": "manage_modeling",
        "materyaller": "manage_materials",
        "materyal": "manage_materials",
        # render already defined in English defaults implicitly or elsewhere? No, check.
        "dışa_aktar": "manage_export",
        "disa_aktar": "manage_export",
        "toplu": "manage_batch",
        # Spanish
        "animación": "manage_animation",
        "animacion": "manage_animation",
        "escena": "manage_scene",
        "objetos": "manage_objects",
        "modelado": "manage_modeling",
        "materiales": "manage_materials",
        "renderizado": "manage_rendering",
        "exportar": "manage_export",
        "lote": "manage_batch",
        # French
        "scène": "manage_scene",
        "objets": "manage_objects",
        "modélisation": "manage_modeling",
        "modelisation": "manage_modeling",
        "matériaux": "manage_materials",
        "materiaux": "manage_materials",
        "rendu": "manage_rendering",
        "exportation": "manage_export",
        "lot": "manage_batch",
        # German
        "szene": "manage_scene",
        "objekte": "manage_objects",
        "modellierung": "manage_modeling",
        "materialien": "manage_materials",
        "rendering": "manage_rendering",
        "exportieren": "manage_export",
        "stapel": "manage_batch",
    }

    # Action aliases
    ACTION_ALIASES = {
        # Common actions - English variations
        "create": "CREATE",
        "add": "CREATE",
        "new": "CREATE",
        "delete": "DELETE",
        "remove": "DELETE",
        "del": "DELETE",
        "update": "UPDATE",
        "modify": "UPDATE",
        "edit": "UPDATE",
        "get": "GET",
        "fetch": "GET",
        "list": "LIST",
        "show": "LIST",
        "display": "LIST",
        # Turkish
        "oluştur": "CREATE",
        "olustur": "CREATE",
        "ekle": "CREATE",
        "sil": "DELETE",
        "güncelle": "UPDATE",
        "guncelle": "UPDATE",
        "düzenle": "UPDATE",
        "duzenle": "UPDATE",
        "al": "GET",
        "listele": "LIST",
        # Spanish
        "crear": "CREATE",
        "eliminar": "DELETE",
        "actualizar": "UPDATE",
        "obtener": "GET",
        "listar": "LIST",
        # French
        "créer": "CREATE",
        "creer": "CREATE",
        "supprimer": "DELETE",
        "mettre_à_jour": "UPDATE",
        "mettre_a_jour": "UPDATE",
        "obtenir": "GET",
        "lister": "LIST",
        # German
        "erstellen": "CREATE",
        "löschen": "DELETE",
        "loschen": "DELETE",
        "aktualisieren": "UPDATE",
        "abrufen": "GET",
        "auflisten": "LIST",
    }

    @classmethod
    def resolve_tool(cls, name: str) -> Optional[str]:
        """
        Resolve tool name alias to canonical name.

        Examples:
            >>> MultiLanguageResolver.resolve_tool("animasyon")
            "manage_animation"

            >>> MultiLanguageResolver.resolve_tool("scene")
            "manage_scene"
        """
        name_lower = name.lower().strip()

        # Direct match
        if name_lower in cls.TOOL_ALIASES:
            return cls.TOOL_ALIASES[name_lower]

        # Try with manage_ prefix
        if not name_lower.startswith("manage_"):
            with_prefix = f"manage_{name_lower}"
            if with_prefix in cls.TOOL_ALIASES.values():
                return with_prefix

        # Try fuzzy match
        from .fuzzy_matcher import find_best_match

        all_names = list(set(cls.TOOL_ALIASES.values()))
        return find_best_match(name_lower, all_names, threshold=0.7)

    @classmethod
    def resolve_action(cls, action: str) -> Optional[str]:
        """Resolve action alias to canonical action name."""
        action_upper = action.upper().strip()

        # Direct match
        if action_upper in cls.ACTION_ALIASES:
            return cls.ACTION_ALIASES[action_upper]

        # Try direct uppercase
        return action_upper


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def get_tool_catalog(category: Optional[str] = None) -> Dict[str, Any]:
    """Get complete tool catalog."""
    catalog = ToolCatalog()
    return catalog.get_catalog(category)


def search_tools(query: str) -> List[Dict[str, Any]]:
    """Search tools by query."""
    catalog = ToolCatalog()
    results = catalog.search(query)

    return [
        {"tool": name, "score": round(score, 2), "info": catalog.get_tool(name)}
        for name, score in results
    ]


def get_action_help(tool_name: str, action: str) -> Optional[Dict[str, Any]]:
    """Get help for a specific action."""
    catalog = ToolCatalog()
    return catalog.get_action_help(tool_name, action)


def resolve_tool_alias(name: str) -> Optional[str]:
    """Resolve tool name alias."""
    return MultiLanguageResolver.resolve_tool(name)


def resolve_action_alias(action: str) -> Optional[str]:
    """Resolve action alias."""
    return MultiLanguageResolver.resolve_action(action)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "ActionDiscovery",
    "SchemaGenerator",
    "ExampleGenerator",
    "ToolCatalog",
    "ToolInfo",
    "ActionInfo",
    "MultiLanguageResolver",
    "get_tool_catalog",
    "search_tools",
    "get_action_help",
    "resolve_tool_alias",
    "resolve_action_alias",
]
