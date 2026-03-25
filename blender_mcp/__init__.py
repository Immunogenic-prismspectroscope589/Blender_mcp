bl_info = {
    "name": "Blender MCP",
    "author": "GÖKSEL ÖZKAN (GitHub: glonorce)",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),  # High Mode: Blender 5.0+ only, no backward compatibility
    "location": "View3D > Sidebar > MCP",
    "description": "Blender Model Context Protocol (MCP) Server - High Mode Vision Edition (v1.0.0)",
    "category": "Development",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/glonorce/blender-mcp",
    "tracker_url": "https://github.com/glonorce/blender-mcp/issues",
}


# Try to import bpy, if it fails (running outside Blender), create a mock.
# This allows the MCP server to start and list tools even in a standard Python env.
import sys
from types import ModuleType
from typing import cast, Optional, Any
from unittest.mock import MagicMock


def _ensure_bpy_contract(bpy_module):
    """Guarantee minimum bpy contract for headless/CI environments."""
    patched = False
    for attr in ("ops", "props", "types", "context", "data", "path"):
        if not hasattr(bpy_module, attr):
            setattr(bpy_module, attr, MagicMock(name=f"bpy.{attr}"))
            patched = True

    if not hasattr(bpy_module, "app"):
        mock_app = MagicMock(name="bpy.app")
        mock_app.background = False
        mock_app.version = (0, 0, 0)
        setattr(bpy_module, "app", mock_app)
        patched = True

    sys.modules.setdefault("bpy.props", getattr(bpy_module, "props"))
    sys.modules.setdefault("bpy.types", getattr(bpy_module, "types"))
    sys.modules.setdefault("bpy.ops", getattr(bpy_module, "ops"))
    sys.modules.setdefault("bpy.context", getattr(bpy_module, "context"))

    path_module = getattr(bpy_module, "path")
    if not hasattr(path_module, "abspath"):
        setattr(path_module, "abspath", lambda p: p)
        patched = True

    if "bmesh" not in sys.modules:
        sys.modules["bmesh"] = MagicMock(name="bmesh")

    if "mathutils" not in sys.modules:
        mock_mathutils = MagicMock(name="mathutils")
        mock_mathutils.Vector = MagicMock
        mock_mathutils.Matrix = MagicMock
        mock_mathutils.Quaternion = MagicMock
        mock_mathutils.Color = MagicMock
        sys.modules["mathutils"] = mock_mathutils

    return patched


try:
    import bpy

    was_patched = _ensure_bpy_contract(bpy)
    if was_patched and not hasattr(bpy, "is_mock"):
        setattr(bpy, "is_mock", True)
except ImportError:
    mock_bpy = ModuleType("bpy")
    setattr(mock_bpy, "ops", MagicMock(name="bpy.ops"))
    setattr(mock_bpy, "props", MagicMock(name="bpy.props"))
    setattr(mock_bpy, "types", MagicMock(name="bpy.types"))
    setattr(mock_bpy, "context", MagicMock(name="bpy.context"))
    setattr(mock_bpy, "data", MagicMock(name="bpy.data"))
    setattr(mock_bpy, "is_mock", True)
    sys.modules["bpy"] = mock_bpy
    _ensure_bpy_contract(mock_bpy)
    import bpy

if not hasattr(bpy, "is_mock"):
    setattr(bpy, "is_mock", False)

import importlib
import json

# STAFF+ DEBUG LOGGING
import logging
import os
import socket
import sys
import tempfile
import threading
import time
import traceback

SERVER_LOG_FILE = os.path.join(tempfile.gettempdir(), "blender_server_debug.log")
server_logger = logging.getLogger("blender_mcp_server")
server_logger.setLevel(logging.DEBUG)
# Remove old handlers to prevent dupes on reload
if server_logger.hasHandlers():
    server_logger.handlers.clear()
# Rotating handler: 5 MB limit, 3 backups, UTF-8 for Windows compatibility
from logging.handlers import RotatingFileHandler as _RotatingFileHandler

handler = _RotatingFileHandler(
    SERVER_LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
server_logger.addHandler(handler)


def log_debug(msg):
    try:
        server_logger.info(msg)
        # print(f"[MCP DEBUG] {msg}") # DISABLE CONSOLE PRINT to prevent Stdio Corruption
    except:
        pass


log_debug("=== BLENDER SERVER LOADED (V1.0.0 - HIGH MODE UNLEASHED) ===")

# Add the PARENT directory to sys.path to ensure 'blender_mcp' package resolution works
# This is critical for absolute imports like 'from blender_mcp.core import ...'
package_dir = os.path.dirname(os.path.realpath(__file__))  # .../blender_mcp
parent_dir = os.path.dirname(package_dir)  # .../blender-mcp
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# High Mode: Handle missing props gracefully (fake-bpy-module compatibility)
try:
    from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
except ImportError:
    # Fallback for fake-bpy-module or missing props
    def BoolProperty(**kwargs) -> Any:  # type: ignore[misc]
        return cast(Any, "PROPERTY")

    def EnumProperty(**kwargs) -> Any:  # type: ignore[misc]
        return cast(Any, "PROPERTY")

    def FloatProperty(**kwargs) -> Any:  # type: ignore[misc]
        return cast(Any, "PROPERTY")

    def IntProperty(**kwargs) -> Any:  # type: ignore[misc]
        return cast(Any, "PROPERTY")

    def StringProperty(**kwargs) -> Any:  # type: ignore[misc]
        return cast(Any, "PROPERTY")


# Import Dispatcher (Registry)
# We use relative import since we are inside the package
try:
    dispatcher = importlib.import_module(".dispatcher", __package__)
except ImportError:
    # Fallback for some weird Blender path contexts
    dispatcher = importlib.import_module("dispatcher")

# Data for Integration
# SECURITY: API keys must be set via Blender preferences or environment variables


class BlenderMCPServer:
    def __init__(self, host="localhost", port=9879):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None

    def start(self):
        if self.running:
            print("[MCP] Server is already running")
            return

        self.running = True

        try:
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to localhost for security
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)

            # Start server thread
            self.server_thread = threading.Thread(target=self._server_loop)
            self.server_thread.daemon = True
            self.server_thread.start()

            print(f"[MCP] BlenderMCP server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"[MCP] Failed to start server: {str(e)}")
            self.stop()

    def stop(self):
        self.running = False

        # Close socket
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        # Wait for thread to finish
        if self.server_thread:
            try:
                if self.server_thread.is_alive():
                    self.server_thread.join(timeout=1.0)
            except:
                pass
            self.server_thread = None

        print("[MCP] BlenderMCP server stopped")

    def _server_loop(self):
        """Main server loop in a separate thread"""
        print("[MCP] Server thread started")
        if self.socket:
            self.socket.settimeout(1.0)  # Timeout to allow for stopping

        while self.running and self.socket:
            try:
                # Accept new connection
                try:
                    client, address = self.socket.accept()
                    # print(f"[MCP] Connected: {address}")

                    # Handle client in a separate thread
                    client_thread = threading.Thread(target=self._handle_client, args=(client,))
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    # Just check running condition
                    continue
                except Exception as e:
                    print(f"[MCP] Error accepting connection: {str(e)}")
                    time.sleep(0.5)
            except Exception as e:
                print(f"[MCP] Error in server loop: {str(e)}")
                if not self.running:
                    break
                time.sleep(0.5)

        print("[MCP] Server thread stopped")

    def _handle_client(self, client):
        """Handle connected client using Robust Protocol - Blender 5.0+ Fixed"""
        # Ensure we can import the protocol module
        try:
            from .core import protocol
        except ImportError:
            import blender_mcp.core.protocol as protocol

        client.settimeout(None)  # Blocking mode

        log_debug(f"Client Connected: {client.getpeername()}")

        try:
            while self.running:
                # 1. Receive Message (Blocks until full frame arrives)
                try:
                    command = protocol.recv_message(client)
                    if not command:
                        log_debug("Client Disconnected (EOF)")
                        break

                    log_debug(f"Received Command: {str(command)[:100]}...")

                    # 2. Execute command DIRECTLY (we're already in a thread,
                    # execute_command handles thread safety internally)
                    try:
                        log_debug("Executing command...")
                        response = self.execute_command(command)
                        log_debug(f"Execution Done. Response: {str(response)[:100]}...")

                        # 3. Send Response
                        protocol.send_message(client, response)
                        log_debug("Response SENT.")
                    except Exception as e:
                        log_debug(f"Error executing/sending: {str(e)}")
                        log_debug(traceback.format_exc())
                        # Try to send error frame
                        try:
                            protocol.send_message(
                                client,
                                {
                                    "status": "error",
                                    "message": f"Execution Error: {str(e)}",
                                },
                            )
                        except:
                            pass

                except socket.timeout:
                    continue
                except Exception as e:
                    log_debug(f"Transport Error: {e}")
                    log_debug(traceback.format_exc())
                    break

        except Exception as e:
            log_debug(f"Error in client handler: {str(e)}")
            log_debug(traceback.format_exc())
        finally:
            log_debug("Closing Client Connection")
            try:
                client.close()
            except:
                pass

    def execute_command(self, command):
        """Execute a command with detailed error handling"""
        try:
            log_debug(f"execute_command started for: {command.get('tool', 'unknown')}")
            result = self._execute_command_internal(command)
            log_debug("execute_command completed successfully")
            return result
        except Exception as e:
            error_msg = f"Command execution failed: {str(e)}"
            log_debug(f"ERROR: {error_msg}")
            log_debug(traceback.format_exc())
            return {"status": "error", "message": error_msg}

    def _execute_command_internal(self, command):
        """Internal command execution using modular dispatch system"""
        cmd_type = command.get("type") or command.get("tool")  # Support both formats
        command.get("params", {})

        # Normalize command structure for dispatcher
        if not command.get("tool"):
            command["tool"] = cmd_type

        # Use modular handler system
        try:
            # Dispatch command to registry
            # We pass self (ctx) to the dispatcher
            result = dispatcher.dispatch_command(command, ctx=self)

            # Check for error dict
            if isinstance(result, dict) and "error" in result:
                # If unknown, try legacy fallback (only for telemetry)
                if "unknown command" in str(result["error"]).lower():
                    if cmd_type == "get_telemetry_consent":
                        return {
                            "status": "success",
                            "result": self.get_telemetry_consent(),
                        }

            if isinstance(result, dict) and "error" in result:
                return {"status": "error", "message": result["error"]}

            return {"status": "success", "result": result}

        except Exception as e:
            print(f"[MCP] Modular handler error for {cmd_type}: {e}")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def get_telemetry_consent(self):
        """Get the current telemetry consent status"""
        try:
            addon_prefs = bpy.context.preferences.addons.get(__package__)  # type: ignore[union-attr] # Use package name
            if addon_prefs:
                consent = cast(Any, addon_prefs).preferences.telemetry_consent
            else:
                consent = True
        except (AttributeError, KeyError):
            consent = True
        return {"consent": consent}


class BLENDERMCP_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__  # Use package name for preferences

    telemetry_consent: bool = cast(
        bool,
        BoolProperty(
            name="Allow Telemetry",
            description="Allow collection of anonymized usage data",
            default=True,
        ),
    )

    safe_mode: bool = cast(
        bool,
        BoolProperty(
            name="Safe Mode",
            description="Prevent execution of arbitrary Python code. Recommended for shared environments.",
            default=True,
        ),
    )

    def draw(self, context):
        layout = self.layout

        # Security Section
        layout.label(text="Security:", icon="LOCKED")
        box = layout.box()
        box.prop(self, "safe_mode", text="Safe Mode (Disable Python Execution)")
        if self.safe_mode:
            box.label(text="Arbitrary code execution is BLOCKED.", icon="CHECKMARK")
        else:
            box.label(
                text="Arbitrary code execution is ALLOWED. Use with caution!",
                icon="ERROR",
            )

        # Telemetry section
        layout.label(text="Telemetry & Privacy:", icon="PREFERENCES")

        box = layout.box()
        box.prop(self, "telemetry_consent", text="Allow Telemetry")

        # Terms link
        box.separator()
        box.operator("blendermcp.open_terms", text="View Terms and Conditions", icon="TEXT")


# Blender UI Panel
class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label = "Blender MCP"
    bl_idname = "BLENDERMCP_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "BlenderMCP"

    def draw(self, context):
        layout = self.layout
        if not layout:
            return
        scene = context.scene

        if scene:
            layout.prop(scene, "blendermcp_port")

        # Security Indicator
        prefs_addon = None
        if context.preferences and context.preferences.addons:
            prefs_addon = context.preferences.addons.get(__package__)

        if prefs_addon:
            prefs = prefs_addon.preferences
            if prefs.safe_mode:
                layout.label(text="Safe Mode: ON", icon="LOCKED")
            else:
                layout.label(text="Safe Mode: OFF", icon="ERROR")

        layout.separator()

        if scene:
            # Integration Toggles
            layout.prop(scene, "blendermcp_use_polyhaven", text="Poly Haven Integration")
            layout.prop(scene, "blendermcp_use_hyper3d", text="Hyper3D Rodin Integration")

            if scene.blendermcp_use_hyper3d:
                box = layout.box()
                if box:
                    box.prop(scene, "blendermcp_hyper3d_mode", text="Mode")
                    box.prop(scene, "blendermcp_hyper3d_api_key", text="API Key")

            layout.prop(scene, "blendermcp_use_sketchfab", text="Sketchfab Integration")
            if scene.blendermcp_use_sketchfab:
                layout.prop(scene, "blendermcp_sketchfab_api_key", text="API Key")

            layout.prop(scene, "blendermcp_use_hunyuan3d", text="Hunyuan3D Integration")

            if scene.blendermcp_use_hunyuan3d:
                box = layout.box()
                if box:
                    box.prop(scene, "blendermcp_hunyuan3d_mode", text="Mode")
                    if scene.blendermcp_hunyuan3d_mode == "OFFICIAL_API":
                        box.prop(scene, "blendermcp_hunyuan3d_secret_id", text="Secret ID")
                        box.prop(scene, "blendermcp_hunyuan3d_secret_key", text="Secret Key")
                    else:
                        box.prop(scene, "blendermcp_hunyuan3d_api_url", text="API URL")

                    box.prop(
                        scene,
                        "blendermcp_hunyuan3d_octree_resolution",
                        text="Octree Resolution",
                    )
                    box.prop(
                        scene,
                        "blendermcp_hunyuan3d_num_inference_steps",
                        text="Inference Steps",
                    )
                    box.prop(scene, "blendermcp_hunyuan3d_guidance_scale", text="Guidance Scale")
                    box.prop(scene, "blendermcp_hunyuan3d_texture", text="Generate Texture")

        layout.separator()

        if not scene.blendermcp_server_running:
            try:
                layout.operator(
                    "blendermcp.start_server", text="Connect to MCP server", icon="LINKED"
                )
            except:
                pass
        else:
            try:
                layout.operator("blendermcp.stop_server", text="Disconnect", icon="UNLINKED")
                layout.label(text=f"Running on port {scene.blendermcp_port}")
            except:
                pass


# Operator to start the server
class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "Connect to Claude"
    bl_description = "Start the BlenderMCP server to connect with Claude"

    def execute(self, context):
        scene = context.scene

        # Create a new server instance
        if not hasattr(bpy.types, "blendermcp_server") or not getattr(
            bpy.types, "blendermcp_server", None
        ):
            setattr(bpy.types, "blendermcp_server", BlenderMCPServer(port=scene.blendermcp_port))

        # Start the server
        server = getattr(bpy.types, "blendermcp_server", None)
        if server:
            server.start()
        # scene.blendermcp_server_running = True # This relies on UI update

        return {"FINISHED"}


# Operator to stop the server
class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop the connection to Claude"
    bl_description = "Stop the connection to Claude"

    def execute(self, context):
        # Stop the server if it exists
        if hasattr(bpy.types, "blendermcp_server") and bpy.types.blendermcp_server:
            bpy.types.blendermcp_server.stop()
            del bpy.types.blendermcp_server

        # scene.blendermcp_server_running = False

        return {"FINISHED"}


# Operator to open Terms and Conditions
class BLENDERMCP_OT_OpenTerms(bpy.types.Operator):
    bl_idname = "blendermcp.open_terms"
    bl_label = "View Terms and Conditions"
    bl_description = "Open the Terms and Conditions document"

    def execute(self, context):
        terms_url = "https://github.com/glonorce/blender-mcp/blob/main/LICENSE"
        try:
            import webbrowser

            webbrowser.open(terms_url)
            self.report({"INFO"}, "Terms and Conditions opened in browser")
        except Exception as e:
            self.report({"ERROR"}, f"Could not open Terms and Conditions: {str(e)}")

        return {"FINISHED"}


class BLENDERMCP_OT_DebugTools(bpy.types.Operator):
    bl_idname = "blendermcp.debug_tools"
    bl_label = "Debug Tools List"
    bl_description = "Print list of registered tools to console"

    def execute(self, context):
        tools = dispatcher.list_all_tools()
        print("[MCP] Registered Tools:")
        print(json.dumps(tools, indent=2))
        self.report({"INFO"}, f"Logged {tools['count']} tools to console")
        return {"FINISHED"}


classes = (
    BLENDERMCP_OT_StartServer,
    BLENDERMCP_OT_StopServer,
    BLENDERMCP_OT_OpenTerms,
    BLENDERMCP_OT_DebugTools,
    BLENDERMCP_AddonPreferences,
    BLENDERMCP_PT_Panel,
)


def register():
    """Register the Blender MCP add-on."""
    log_debug("[MCP] Registering Blender MCP add-on...")
    print("[MCP] Registering Blender MCP add-on 1.0.0...")

    try:
        # Load modular handlers with detailed logging
        try:
            log_debug("[MCP] Starting handler loading...")
            print("[MCP] Loading handlers...")
            dispatcher.load_handlers()
            handler_count = len(dispatcher.HANDLER_REGISTRY)
            log_debug(f"[MCP] Loaded {handler_count} handlers")
            print(f"[MCP] Successfully loaded {handler_count} handlers")
        except Exception as e:
            error_detail = traceback.format_exc()
            log_debug(f"[MCP] Failed to load handlers: {e}")
            log_debug(f"[MCP] Traceback: {error_detail}")
            print(f"[MCP] ERROR: Handler loading failed: {e}")
            print(error_detail)

        # Register classes
        for cls in classes:
            try:
                bpy.utils.register_class(cls)
            except Exception as e:
                log_debug(f"[MCP] Failed to register class {cls.__name__}: {e}")
                raise  # Re-raise to prevent partial registration

        # Properties - with safe deletion first (in case of reload)
        properties_to_add = [
            (
                "blendermcp_port",
                IntProperty(  # type: ignore[func-returns-value]
                    name="Port",
                    description="Port for the BlenderMCP server",
                    default=9879,
                    min=1024,
                    max=65535,
                    subtype="UNSIGNED",
                ),
            ),
            (
                "blendermcp_server_running",
                BoolProperty(  # type: ignore[func-returns-value]
                    name="Server Running",
                    get=lambda self: (
                        hasattr(bpy.types, "blendermcp_server")
                        and bpy.types.blendermcp_server
                        and bpy.types.blendermcp_server.running
                    ),
                ),
            ),
            # Integration Properties
            (
                "blendermcp_use_polyhaven",
                BoolProperty(name="Use assets from Poly Haven", default=False),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_use_sketchfab",
                BoolProperty(name="Use assets from Sketchfab", default=False),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_sketchfab_api_key",
                StringProperty(name="API Key", default="", subtype="PASSWORD"),  # type: ignore[func-returns-value]
            ),
            ("blendermcp_use_hyper3d", BoolProperty(name="Use Hyper3D", default=False)),  # type: ignore[func-returns-value]
            (
                "blendermcp_hyper3d_mode",
                EnumProperty(  # type: ignore[func-returns-value]
                    items=[("MAIN_SITE", "Main Site", ""), ("FAL_AI", "Fal AI", "")],
                    name="Mode",
                    default="MAIN_SITE",
                ),
            ),
            (
                "blendermcp_hyper3d_api_key",
                StringProperty(name="API Key", default="", subtype="PASSWORD"),  # type: ignore[func-returns-value]
            ),
            ("blendermcp_use_hunyuan3d", BoolProperty(name="Use Hunyuan3D", default=False)),  # type: ignore[func-returns-value]
            (
                "blendermcp_hunyuan3d_mode",
                EnumProperty(  # type: ignore[func-returns-value]
                    items=[("OFFICIAL_API", "Official API", ""), ("LOCAL_API", "Local API", "")],
                    name="Mode",
                    default="OFFICIAL_API",
                ),
            ),
            (
                "blendermcp_hunyuan3d_secret_id",
                StringProperty(name="Secret ID", default="", subtype="PASSWORD"),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_hunyuan3d_secret_key",
                StringProperty(name="Secret Key", default="", subtype="PASSWORD"),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_hunyuan3d_api_url",
                StringProperty(name="API URL", default="http://127.0.0.1:8080"),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_hunyuan3d_octree_resolution",
                IntProperty(name="Octree Resolution", default=256),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_hunyuan3d_num_inference_steps",
                IntProperty(name="Number of Inference Steps", default=50),  # type: ignore[func-returns-value]
            ),
            (
                "blendermcp_hunyuan3d_guidance_scale",
                FloatProperty(name="Guidance Scale", default=5.0),  # type: ignore[func-returns-value]
            ),
            ("blendermcp_hunyuan3d_texture", BoolProperty(name="Generate Texture", default=True)),  # type: ignore[func-returns-value]
        ]

        for prop_name, prop_value in properties_to_add:
            try:
                # Remove if exists (for reload safety)
                if hasattr(bpy.types.Scene, prop_name):
                    delattr(bpy.types.Scene, prop_name)
                setattr(bpy.types.Scene, prop_name, prop_value)
            except Exception as e:
                log_debug(f"[MCP] Failed to add property {prop_name}: {e}")
                raise

        log_debug("[MCP] Blender MCP add-on registered successfully")

    except Exception as e:
        log_debug(f"[MCP] Critical error during registration: {e}")
        log_debug(traceback.format_exc())
        raise  # Re-raise to signal Blender that registration failed


def unregister():
    """Unregister the Blender MCP add-on."""
    log_debug("[MCP] Unregistering Blender MCP add-on...")

    try:
        # Stop ThreadSafety monitor thread and remove depsgraph hook
        try:
            from blender_mcp.core.thread_safety import ThreadSafety

            ts = ThreadSafety._instance
            if ts is not None:
                ts._stop_monitor.set()
            # Remove MCP depsgraph hook
            hooks = bpy.app.handlers.depsgraph_update_post
            hooks[:] = [h for h in hooks if getattr(h, "__name__", "") != "_mcp_depsgraph_hook"]
        except Exception as _e:
            log_debug(f"[MCP] ThreadSafety cleanup error: {_e}")

        # Stop server first
        if hasattr(bpy.types, "blendermcp_server") and getattr(
            bpy.types, "blendermcp_server", None
        ):
            try:
                getattr(bpy.types, "blendermcp_server").stop()
                log_debug("[MCP] Server stopped")
            except Exception as e:
                log_debug(f"[MCP] Error stopping server: {e}")
            finally:
                try:
                    delattr(bpy.types, "blendermcp_server")
                except:
                    pass

        # Unregister classes
        for cls in reversed(classes):
            try:
                bpy.utils.unregister_class(cls)  # type: ignore[arg-type]
            except Exception as e:
                log_debug(f"[MCP] Error unregistering class {cls.__name__}: {e}")

        # Remove properties
        properties_to_remove = [
            "blendermcp_port",
            "blendermcp_server_running",
            "blendermcp_use_polyhaven",
            "blendermcp_use_sketchfab",
            "blendermcp_sketchfab_api_key",
            "blendermcp_use_hyper3d",
            "blendermcp_hyper3d_mode",
            "blendermcp_hyper3d_api_key",
            "blendermcp_use_hunyuan3d",
            "blendermcp_hunyuan3d_mode",
            "blendermcp_hunyuan3d_secret_id",
            "blendermcp_hunyuan3d_secret_key",
            "blendermcp_hunyuan3d_api_url",
            "blendermcp_hunyuan3d_octree_resolution",
            "blendermcp_hunyuan3d_num_inference_steps",
            "blendermcp_hunyuan3d_guidance_scale",
            "blendermcp_hunyuan3d_texture",
        ]

        for prop in properties_to_remove:
            try:
                if hasattr(bpy.types.Scene, prop):
                    delattr(bpy.types.Scene, prop)
            except Exception as e:
                log_debug(f"[MCP] Error removing property {prop}: {e}")

        log_debug("[MCP] Blender MCP add-on unregistered successfully")

    except Exception as e:
        log_debug(f"[MCP] Error during unregistration: {e}")
        log_debug(traceback.format_exc())


if __name__ == "__main__":
    register()
