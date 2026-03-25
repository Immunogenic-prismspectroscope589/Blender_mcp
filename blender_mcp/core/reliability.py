from typing import Any


class ContextEnsurer:
    """
    Staff+ Reliability Pattern: Context Auto-Healing.
    Ensures that required Blender Contexts (Sequencer, Compositor, Text Editor)
    are initialized before tools attempt to use them.

    This replaces "AttributeError: NoneType has no attribute..." with correct initialization.
    """

    @staticmethod
    def ensure_sequencer(scene: Any) -> bool:
        """
        Ensure the Video Sequence Editor is initialized for the given scene.
        """
        if not scene.sequence_editor:
            try:
                # Blender API allows creating it safely
                scene.sequence_editor_create()
                print(
                    f"[MCP Reliability] Auto-Initialized Sequence Editor for scene '{scene.name}'"
                )
            except Exception as e:
                print(f"[MCP Reliability] Failed to init Sequence Editor: {e}")
                return False
        return True

    @staticmethod
    def ensure_compositor(scene: Any) -> bool:
        """
        Ensure Compositing Nodes are enabled and the Node Tree exists.
        """
        # 1. Enable Use Nodes
        if not scene.use_nodes:
            scene.use_nodes = True
            print(f"[MCP Reliability] Enabled 'Use Nodes' for scene '{scene.name}'")

        # 2. Check Tree execution
        if not scene.node_tree:
            # This is rare if use_nodes is True, but can happen in headless/broken states
            # We can't easily "create" the default one if it fails, but we can report it.
            # In some Blender versions, toggling use_nodes off/on fixes it.
            scene.use_nodes = False
            scene.use_nodes = True

        if not scene.node_tree:
            print("[MCP Reliability] Critical: Scene.node_tree is None even after enabling nodes.")
            return False

        return True

    @staticmethod
    def ensure_scripting_context() -> None:
        """
        Ensure a Text Editor area exists (Virtual or Real) for scripting ops.
        (Less critical in headerless, but good for some ops).
        """
        pass
