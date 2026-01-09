#!/usr/bin/env python3
"""
MCP Server for controlling the Finance App PyQt6 application.

This server translates MCP tool calls to control protocol commands that
are sent to the Finance App's embedded control server via TCP.

Usage:
    python mcp_server/pyqt_mcp.py

The server expects the Finance App to be running with its control server
enabled on localhost:9999 (default).
"""

import json
import socket
import subprocess
import time
import os
import sys
from typing import Dict, Any, Optional, List

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FinanceApp-Control-Server")

# Configuration from environment variables
DEFAULT_HOST = os.getenv("PYQT_CONTROL_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("PYQT_CONTROL_PORT", "29999"))
APP_PATH = os.getenv("PYQT_APP_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))

_app_process: Optional[subprocess.Popen] = None
_launched_port: Optional[int] = None  # Track port of launched instance


def _get_effective_port(port: int) -> int:
    """Get the effective port - use launched port if available and default was passed."""
    global _launched_port
    if port == DEFAULT_PORT and _launched_port is not None:
        return _launched_port
    return port


# =============================================================================
# Workspace Management Helpers (for Regolith/i3wm)
# =============================================================================

def _get_available_workspace(min_ws: int = 100, max_ws: int = 120) -> Optional[int]:
    """Find the first available workspace (not currently in use) in the given range."""
    try:
        result = subprocess.run(
            ["i3-msg", "-t", "get_workspaces"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            workspaces = json.loads(result.stdout)
            used = {ws.get("num") for ws in workspaces}
            for num in range(min_ws, max_ws + 1):
                if num not in used:
                    return num
        return None
    except Exception:
        return min_ws  # Fallback


def _get_window_con_id(window_title: str) -> Optional[int]:
    """Get the i3 container ID for a window by its title."""
    try:
        result = subprocess.run(
            ["i3-msg", "-t", "get_tree"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None

        tree = json.loads(result.stdout)

        def find_con_id(node):
            title = node.get('window_properties', {}).get('title', '')
            if title == window_title:
                return node.get('id')
            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                found = find_con_id(child)
                if found:
                    return found
            return None

        return find_con_id(tree)
    except Exception:
        return None


def _move_container_to_workspace(con_id: int, workspace: int) -> bool:
    """Move a container by ID to specified workspace (without stealing focus)."""
    try:
        result = subprocess.run(
            ["i3-msg", f"[con_id={con_id}] move container to workspace number {workspace}"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def _is_i3_available() -> bool:
    """Check if i3-msg is available on the system."""
    try:
        result = subprocess.run(
            ["which", "i3-msg"],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def _send_command(
    command: Dict[str, Any],
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """Send a command to the Finance App and return the response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30.0)

    try:
        sock.connect((host, port))

        command_json = json.dumps(command) + "\n"
        sock.sendall(command_json.encode('utf-8'))

        response_data = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
            if b"\n" in response_data:
                break

        return json.loads(response_data.decode('utf-8').strip())
    finally:
        sock.close()


def _is_app_running(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Check if the app control server is responding."""
    try:
        response = _send_command({"type": "get_window_info"}, host, port)
        return response.get("status") == "success"
    except Exception:
        return False


@mcp.tool()
def launch_app(
    app_path: str = "",
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    wait_time: float = 3.0
) -> Dict[str, Any]:
    """
    Launch the Finance App application on a dedicated workspace.

    Args:
        app_path: Path to the application's main.py file (uses default if empty)
        host: Control server host (default: localhost)
        port: Control server port - if DEFAULT_PORT, auto-assigns based on workspace (10100-10120)
        wait_time: Seconds to wait for app to start (default: 3.0)

    Returns:
        Dict with status, message, window_title, workspace, and port on success
    """
    global _app_process, _launched_port

    if not app_path:
        app_path = APP_PATH

    if not app_path or not os.path.exists(app_path):
        return {"status": "error", "message": f"Application not found: {app_path}"}

    try:
        # Check if i3wm is available for workspace management
        use_workspace_management = _is_i3_available()

        target_workspace = None
        actual_port = port
        client_id = None

        if use_workspace_management:
            # Find available workspace in range 100-120
            target_workspace = _get_available_workspace(100, 120)
            if target_workspace is None:
                return {"status": "error", "message": "No available workspace in range 100-120"}

            # Auto-assign port if using default (workspace 100 = port 10100)
            if port == DEFAULT_PORT:
                actual_port = 10000 + target_workspace  # e.g., 10100, 10101, ...

            # Use workspace number as client_id to avoid IB connection conflicts
            client_id = target_workspace

            # Check if already running on this port
            if _is_app_running(host, actual_port):
                _launched_port = actual_port  # Track the port
                return {
                    "status": "success",
                    "message": f"Application is already running on port {actual_port}",
                    "already_running": True,
                    "port": actual_port
                }
        else:
            # No i3wm - check if already running on the specified port
            if _is_app_running(host, actual_port):
                _launched_port = actual_port  # Track the port
                return {
                    "status": "success",
                    "message": "Application is already running",
                    "already_running": True,
                    "port": actual_port
                }

        # Build command with workspace and client-id arguments if applicable
        cmd = [sys.executable, app_path, "--host", host, "--port", str(actual_port)]
        if target_workspace is not None:
            cmd.extend(["--workspace", str(target_workspace)])
        if client_id is not None:
            cmd.extend(["--client-id", str(client_id)])

        # Launch app (opens on current workspace initially)
        _app_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.path.dirname(app_path)
        )

        # Wait for the app to start
        time.sleep(wait_time)

        # Check if process is still running
        if _app_process.poll() is not None:
            stdout, stderr = _app_process.communicate()
            return {
                "status": "error",
                "message": f"App failed to start: {stderr.decode()}"
            }

        # Verify connection and get window title
        response = _send_command({"type": "get_snapshot"}, host, actual_port)
        if response.get("status") != "success":
            return {"status": "error", "message": "App started but not responding"}

        result = response.get("result", {})
        window_title = result.get("window_title")

        # Move window to dedicated workspace using con_id (no focus steal)
        if use_workspace_management and window_title and target_workspace is not None:
            con_id = _get_window_con_id(window_title)
            if con_id:
                _move_container_to_workspace(con_id, target_workspace)

        # Track the launched port for subsequent tool calls
        _launched_port = actual_port

        response_data = {
            "status": "success",
            "message": f"Application launched on {host}:{actual_port}",
            "window_title": window_title,
            "widget_count": len(result.get("widgets", [])),
            "port": actual_port
        }

        if target_workspace is not None:
            response_data["message"] = f"Application launched on workspace {target_workspace} (port {actual_port})"
            response_data["workspace"] = target_workspace

        return response_data

    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def close_app(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Close the Finance App application.

    Args:
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    global _app_process, _launched_port

    effective_port = _get_effective_port(port)

    try:
        _send_command({"type": "close"}, host, effective_port)
    except Exception:
        pass  # App might already be closing

    if _app_process:
        time.sleep(0.5)
        if _app_process.poll() is None:
            _app_process.terminate()
            time.sleep(0.5)
            if _app_process.poll() is None:
                _app_process.kill()
        _app_process = None

    # Clear launched port tracking if closing the launched instance
    if effective_port == _launched_port:
        _launched_port = None

    return {"status": "success", "message": "Application closed"}


@mcp.tool()
def get_snapshot(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Get a snapshot of the current UI state.

    Returns all widgets with their properties including:
    - object_name: The unique identifier for the widget
    - type: Widget class name (QPushButton, QLineEdit, etc.)
    - visible: Whether the widget is visible
    - enabled: Whether the widget is enabled
    - Additional properties depending on widget type (text, checked, value, etc.)

    Also returns menu_actions which lists all available menu actions.

    Args:
        host: Control server host
        port: Control server port

    Returns:
        Dict with window info, widgets list, and menu actions
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command({"type": "get_snapshot"}, host, effective_port)
        if response.get("status") == "success":
            return response.get("result", {})
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def click(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Click on a widget by its object name.

    Works with: QPushButton, QCheckBox, QRadioButton

    Args:
        object_name: The Qt object name of the widget (e.g., "submit_button")
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "click", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "message": f"Clicked {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def fill(
    object_name: str,
    text: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Fill text into an input field.

    Works with: QLineEdit, QTextEdit, QPlainTextEdit

    Args:
        object_name: The Qt object name of the input field
        text: The text to enter
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "fill", "object_name": object_name, "text": text},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "message": f"Filled '{text}' into {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def clear(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Clear the text from an input field.

    Works with: QLineEdit, QTextEdit, QPlainTextEdit

    Args:
        object_name: The Qt object name of the input field
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "clear", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "message": f"Cleared {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_text(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Get text from a widget.

    Works with: QLabel, QLineEdit, QPushButton, QCheckBox, QRadioButton,
                QTextEdit, QPlainTextEdit, QComboBox

    Args:
        object_name: The Qt object name of the widget
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and text value
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "get_text", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "text": response.get("result")}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def set_checkbox(
    object_name: str,
    checked: bool,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Set a checkbox or radio button to checked or unchecked.

    Works with: QCheckBox, QRadioButton

    Args:
        object_name: The Qt object name of the checkbox
        checked: True to check, False to uncheck
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "set_checkbox", "object_name": object_name, "checked": checked},
            host, effective_port
        )
        if response.get("status") == "success":
            state = "checked" if checked else "unchecked"
            return {"status": "success", "message": f"Set {object_name} to {state}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_checkbox_state(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Get the checked state of a checkbox or radio button.

    Works with: QCheckBox, QRadioButton

    Args:
        object_name: The Qt object name of the checkbox
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and checked state
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "get_checkbox_state", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "checked": response.get("result")}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def select_combo(
    object_name: str,
    value: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Select a value in a combo box by text.

    Works with: QComboBox

    Args:
        object_name: The Qt object name of the combo box
        value: The text of the item to select
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "select_combo", "object_name": object_name, "value": value},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "message": f"Selected '{value}' in {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_combo_items(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Get all items from a combo box.

    Works with: QComboBox

    Args:
        object_name: The Qt object name of the combo box
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and list of items
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "get_combo_items", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "items": response.get("result")}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def select_tab(
    object_name: str,
    index: int,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Select a tab in a tab widget by index.

    Works with: QTabWidget

    Args:
        object_name: The Qt object name of the tab widget
        index: The index of the tab to select (0-based)
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "select_tab", "object_name": object_name, "index": index},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "message": f"Selected tab {index} in {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_table_data(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Get data from a table widget.

    Works with: QTableWidget, QTableView

    Args:
        object_name: The Qt object name of the table
        host: Control server host
        port: Control server port

    Returns:
        Dict with headers, rows, row_count, and column_count
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "get_table_data", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", **response.get("result", {})}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def click_table_cell(
    object_name: str,
    row: int,
    column: int,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Click on a specific cell in a table.

    Works with: QTableWidget, QTableView

    Args:
        object_name: The Qt object name of the table
        row: The row index (0-based)
        column: The column index (0-based)
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {
                "type": "click_table_cell",
                "object_name": object_name,
                "row": row,
                "column": column
            },
            host, effective_port
        )
        if response.get("status") == "success":
            return {
                "status": "success",
                "message": f"Clicked cell ({row}, {column}) in {object_name}"
            }
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def trigger_action(
    object_name: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Trigger a menu action by its object name.

    Use get_snapshot() to see available menu_actions and their object names.

    Args:
        object_name: The Qt object name of the action (e.g., "actionHomePage")
        host: Control server host
        port: Control server port

    Returns:
        Dict with status and message
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command(
            {"type": "trigger_action", "object_name": object_name},
            host, effective_port
        )
        if response.get("status") == "success":
            return {"status": "success", "message": f"Triggered action {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_window_info(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT
) -> Dict[str, Any]:
    """
    Get window information (title, size, position, state).

    Args:
        host: Control server host
        port: Control server port

    Returns:
        Dict with window title, size, position, and state
    """
    try:
        effective_port = _get_effective_port(port)
        response = _send_command({"type": "get_window_info"}, host, effective_port)
        if response.get("status") == "success":
            return {"status": "success", **response.get("result", {})}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run(transport='stdio')
