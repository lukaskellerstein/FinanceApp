# Testability via MCP for PyQt/Desktop Applications

This document describes how to make a PyQt6 (or any Qt-based) desktop application testable and controllable by Claude Code via the Model Context Protocol (MCP). This approach is similar to how Playwright MCP controls web browsers.

## Overview

The goal is to enable Claude Code to:
- Launch and close the application
- Inspect the UI state (get a "snapshot" of all widgets)
- Interact with widgets (click buttons, fill inputs, toggle checkboxes)
- Read text from labels and inputs
- Verify application state
- Test the application autonomously

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│   Claude Code   │────▶│   MCP Server     │────▶│  PyQt6 Application      │
│                 │     │  (pyqt_mcp.py)   │     │  + Control Server       │
└─────────────────┘     └──────────────────┘     └─────────────────────────┘
        │                       │                           │
        │    MCP Protocol       │    TCP Socket             │
        │    (stdio)            │    (localhost:9999)       │
        └───────────────────────┴───────────────────────────┘
```

**Components:**
1. **PyQt Application** - Your app with an embedded TCP control server
2. **MCP Server** - Translates MCP tool calls to control protocol commands (configured via `.mcp.json`)
3. **Claude Code** - Uses MCP tools to control the application (permissions via `.claude/settings.json`)

## Implementation Guide

### Step 1: Add Object Names to All Interactive Widgets

Every widget that needs to be interacted with or inspected must have a unique `objectName`. This is how the control server identifies widgets.

```python
# Bad - no object name
button = QPushButton("Submit")

# Good - has object name
button = QPushButton("Submit")
button.setObjectName("submit_button")

# Or inline
self.input_field = QLineEdit()
self.input_field.setObjectName("email_input")
```

**Naming conventions:**
- Use snake_case
- Be descriptive: `login_button`, `username_input`, `status_label`
- For dynamic items, include ID: `todo_checkbox_1`, `delete_button_42`

### Step 2: Add the Control Server to Your Application

Add these classes to your main application file:

```python
import json
import threading
import socketserver
from typing import Optional, Any, Dict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget, QLineEdit, QPushButton, QLabel, QCheckBox, QListWidget


class CommandHandler(QObject):
    """Handles commands from the control server in the Qt main thread."""

    command_received = pyqtSignal(dict, object)

    def __init__(self, main_window: QWidget):
        super().__init__()
        self.app = main_window
        self.command_received.connect(self._handle_command)

    def _handle_command(self, command: dict, response_callback):
        """Handle a command in the Qt thread."""
        try:
            result = self._execute_command(command)
            response_callback({"status": "success", "result": result})
        except Exception as e:
            response_callback({"status": "error", "message": str(e)})

    def _execute_command(self, command: dict) -> Any:
        """Execute a command and return the result."""
        cmd_type = command.get("type")

        if cmd_type == "get_snapshot":
            return self._get_snapshot()
        elif cmd_type == "click":
            return self._click(command.get("object_name"))
        elif cmd_type == "fill":
            return self._fill(command.get("object_name"), command.get("text"))
        elif cmd_type == "get_text":
            return self._get_text(command.get("object_name"))
        elif cmd_type == "get_checkbox_state":
            return self._get_checkbox_state(command.get("object_name"))
        elif cmd_type == "set_checkbox":
            return self._set_checkbox(command.get("object_name"), command.get("checked"))
        elif cmd_type == "clear":
            return self._clear(command.get("object_name"))
        elif cmd_type == "close":
            QTimer.singleShot(100, self.app.close)
            return True
        else:
            raise ValueError(f"Unknown command type: {cmd_type}")

    def _get_snapshot(self) -> Dict:
        """Get a snapshot of all widgets in the application."""
        widgets = []

        def collect_widgets(widget):
            obj_name = widget.objectName()
            if obj_name:
                widget_info = {
                    "object_name": obj_name,
                    "type": widget.__class__.__name__,
                    "visible": widget.isVisible(),
                    "enabled": widget.isEnabled(),
                }

                # Add type-specific info
                if isinstance(widget, QLineEdit):
                    widget_info["text"] = widget.text()
                    widget_info["placeholder"] = widget.placeholderText()
                elif isinstance(widget, QPushButton):
                    widget_info["text"] = widget.text()
                elif isinstance(widget, QLabel):
                    widget_info["text"] = widget.text()
                elif isinstance(widget, QCheckBox):
                    widget_info["checked"] = widget.isChecked()
                    widget_info["text"] = widget.text()
                elif isinstance(widget, QListWidget):
                    widget_info["count"] = widget.count()

                widgets.append(widget_info)

            for child in widget.children():
                if isinstance(child, QWidget):
                    collect_widgets(child)

        collect_widgets(self.app)

        return {
            "window_title": self.app.windowTitle(),
            "window_size": {"width": self.app.width(), "height": self.app.height()},
            "widgets": widgets
        }

    def _find_widget(self, object_name: str) -> Optional[QWidget]:
        """Find a widget by its object name."""
        return self.app.findChild(QWidget, object_name)

    def _click(self, object_name: str) -> bool:
        """Click on a widget."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, (QPushButton, QCheckBox)):
            widget.click()
            return True
        else:
            raise ValueError(f"Widget {object_name} is not clickable")

    def _fill(self, object_name: str, text: str) -> bool:
        """Fill a text input."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QLineEdit):
            widget.setText(text)
            return True
        else:
            raise ValueError(f"Widget {object_name} is not a text input")

    def _clear(self, object_name: str) -> bool:
        """Clear a text input."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QLineEdit):
            widget.clear()
            return True
        else:
            raise ValueError(f"Widget {object_name} is not a text input")

    def _get_text(self, object_name: str) -> str:
        """Get text from a widget."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QLineEdit):
            return widget.text()
        elif isinstance(widget, QLabel):
            return widget.text()
        elif isinstance(widget, QPushButton):
            return widget.text()
        else:
            raise ValueError(f"Widget {object_name} does not have text")

    def _get_checkbox_state(self, object_name: str) -> bool:
        """Get the state of a checkbox."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        else:
            raise ValueError(f"Widget {object_name} is not a checkbox")

    def _set_checkbox(self, object_name: str, checked: bool) -> bool:
        """Set the state of a checkbox."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QCheckBox):
            widget.setChecked(checked)
            return True
        else:
            raise ValueError(f"Widget {object_name} is not a checkbox")


class ControlServerHandler(socketserver.StreamRequestHandler):
    """Handler for control server connections."""

    def handle(self):
        """Handle incoming connections."""
        while True:
            try:
                line = self.rfile.readline()
                if not line:
                    break

                command = json.loads(line.decode('utf-8'))

                response = {}
                event = threading.Event()

                def callback(result):
                    response.update(result)
                    event.set()

                self.server.command_handler.command_received.emit(command, callback)
                event.wait(timeout=30)

                response_json = json.dumps(response) + "\n"
                self.wfile.write(response_json.encode('utf-8'))
                self.wfile.flush()

            except Exception as e:
                error_response = json.dumps({"status": "error", "message": str(e)}) + "\n"
                self.wfile.write(error_response.encode('utf-8'))
                self.wfile.flush()
                break


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded TCP server for handling control connections."""
    allow_reuse_address = True
    daemon_threads = True


def run_control_server(command_handler: CommandHandler, host: str = "localhost", port: int = 9999):
    """Run the control server in a separate thread."""
    server = ThreadedTCPServer((host, port), ControlServerHandler)
    server.command_handler = command_handler

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(f"Control server running on {host}:{port}")
    return server
```

### Step 3: Initialize the Control Server in Your Main Function

```python
import argparse
from PyQt6.QtWidgets import QApplication

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9999, help="Control server port")
    parser.add_argument("--host", type=str, default="localhost", help="Control server host")
    parser.add_argument("--no-server", action="store_true", help="Disable control server")
    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Create your main window
    window = YourMainWindow()
    window.show()

    # Start control server (unless disabled)
    if not args.no_server:
        command_handler = CommandHandler(window)
        control_server = run_control_server(command_handler, args.host, args.port)

    sys.exit(app.exec())
```

### Step 4: Create the MCP Server

Create a file `mcp_server/pyqt_mcp.py`:

```python
#!/usr/bin/env python3
"""MCP Server for controlling PyQt6 applications."""

import json
import socket
import subprocess
import time
import os
import sys
from typing import Dict, Any, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PyQt-Control-Server")

DEFAULT_HOST = os.getenv("PYQT_CONTROL_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("PYQT_CONTROL_PORT", "9999"))
APP_PATH = os.getenv("PYQT_APP_PATH", "")  # Set this to your app's main.py

_app_process: Optional[subprocess.Popen] = None


def _send_command(command: Dict[str, Any], host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """Send a command to the PyQt app and return the response."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(30.0)
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

    sock.close()
    return json.loads(response_data.decode('utf-8').strip())


@mcp.tool()
def launch_app(app_path: str = "", host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, wait_time: float = 2.0) -> Dict[str, Any]:
    """
    Launch the PyQt6 application.

    Args:
        app_path: Path to the application's main.py file
        host: Control server host (default: localhost)
        port: Control server port (default: 9999)
        wait_time: Seconds to wait for app to start

    Returns:
        Dict with status and message
    """
    global _app_process

    if not app_path:
        app_path = APP_PATH

    if not app_path or not os.path.exists(app_path):
        return {"status": "error", "message": f"Application not found: {app_path}"}

    try:
        _app_process = subprocess.Popen(
            [sys.executable, app_path, "--host", host, "--port", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        time.sleep(wait_time)

        if _app_process.poll() is not None:
            stdout, stderr = _app_process.communicate()
            return {"status": "error", "message": f"App failed to start: {stderr.decode()}"}

        response = _send_command({"type": "get_snapshot"}, host, port)
        return {
            "status": "success",
            "message": f"Application launched on {host}:{port}",
            "window_title": response.get("result", {}).get("window_title")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def close_app() -> Dict[str, Any]:
    """Close the PyQt6 application."""
    global _app_process

    try:
        _send_command({"type": "close"})
    except:
        pass

    if _app_process:
        time.sleep(0.5)
        if _app_process.poll() is None:
            _app_process.terminate()
        _app_process = None

    return {"status": "success", "message": "Application closed"}


@mcp.tool()
def get_snapshot(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Get a snapshot of the current UI state.

    Returns all widgets with their properties (object_name, type, text, visible, enabled, etc.)
    """
    try:
        response = _send_command({"type": "get_snapshot"}, host, port)
        if response.get("status") == "success":
            return response.get("result", {})
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def click(object_name: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Click on a widget by its object name.

    Args:
        object_name: The Qt object name of the widget (e.g., "submit_button")
    """
    try:
        response = _send_command({"type": "click", "object_name": object_name}, host, port)
        if response.get("status") == "success":
            return {"status": "success", "message": f"Clicked {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def fill(object_name: str, text: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Fill text into an input field.

    Args:
        object_name: The Qt object name of the input field
        text: The text to enter
    """
    try:
        response = _send_command({"type": "fill", "object_name": object_name, "text": text}, host, port)
        if response.get("status") == "success":
            return {"status": "success", "message": f"Filled '{text}' into {object_name}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_text(object_name: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Get text from a widget (label, button, or input field).

    Args:
        object_name: The Qt object name of the widget
    """
    try:
        response = _send_command({"type": "get_text", "object_name": object_name}, host, port)
        if response.get("status") == "success":
            return {"status": "success", "text": response.get("result")}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def set_checkbox(object_name: str, checked: bool, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Dict[str, Any]:
    """
    Set a checkbox to checked or unchecked.

    Args:
        object_name: The Qt object name of the checkbox
        checked: True to check, False to uncheck
    """
    try:
        response = _send_command({"type": "set_checkbox", "object_name": object_name, "checked": checked}, host, port)
        if response.get("status") == "success":
            return {"status": "success", "message": f"Set {object_name} to {'checked' if checked else 'unchecked'}"}
        return {"status": "error", "message": response.get("message")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    mcp.run(transport='stdio')
```

### Step 5: Configure Dependencies

Create `pyproject.toml`:

```toml
[project]
name = "your-app"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "PyQt6>=6.5.0",
    "mcp[cli]>=1.3.0",
]
```

Install with:
```bash
pip install -e .
# or
uv pip install -e .
```

### Step 6: Configure MCP for Claude Code

Create `.mcp.json` in your project's root directory:

```json
{
  "mcpServers": {
    "pyqt-control": {
      "command": "python3",
      "args": ["mcp_server/pyqt_mcp.py"],
      "env": {
        "PYQT_APP_PATH": "app/main.py"
      }
    }
  }
}
```

Then create/update `.claude/settings.json` in your project root to allow the MCP tools:

```json
{
  "permissions": {
    "allow": [
      "Bash",
      "Edit",
      "Glob",
      "Grep",
      "Read",
      "Write",
      "mcp__pyqt-control"
    ]
  }
}
```

The `mcp__pyqt-control` permission allows all tools from the `pyqt-control` MCP server. You can also be more specific:
- `mcp__pyqt-control__launch_app` - only allow launching
- `mcp__pyqt-control__get_snapshot` - only allow snapshots
- `mcp__pyqt-control__click` - only allow clicking

## Control Protocol Reference

The control server accepts JSON commands over TCP (one per line). Each command has a `type` field.

### Commands

| Command | Fields | Description |
|---------|--------|-------------|
| `get_snapshot` | - | Get all widgets and their properties |
| `click` | `object_name` | Click a button or checkbox |
| `fill` | `object_name`, `text` | Fill text into an input |
| `clear` | `object_name` | Clear an input field |
| `get_text` | `object_name` | Get text from a widget |
| `get_checkbox_state` | `object_name` | Get checkbox checked state |
| `set_checkbox` | `object_name`, `checked` | Set checkbox state |
| `close` | - | Close the application |

### Response Format

```json
{
    "status": "success" | "error",
    "result": <any>,      // Present on success
    "message": "<string>" // Present on error
}
```

### Example: get_snapshot Response

```json
{
    "status": "success",
    "result": {
        "window_title": "My App",
        "window_size": {"width": 800, "height": 600},
        "widgets": [
            {"object_name": "username_input", "type": "QLineEdit", "text": "", "visible": true, "enabled": true},
            {"object_name": "login_button", "type": "QPushButton", "text": "Login", "visible": true, "enabled": true},
            {"object_name": "remember_checkbox", "type": "QCheckBox", "checked": false, "visible": true, "enabled": true}
        ]
    }
}
```

## Extending the Control Server

To add support for additional widget types or custom commands:

1. Add a new command type in `_execute_command()`
2. Implement the handler method (e.g., `_handle_custom_widget()`)
3. Add corresponding MCP tool in `pyqt_mcp.py`

Example for adding ComboBox support:

```python
# In CommandHandler._execute_command()
elif cmd_type == "select_combo":
    return self._select_combo(command.get("object_name"), command.get("value"))

# New method
def _select_combo(self, object_name: str, value: str) -> bool:
    widget = self._find_widget(object_name)
    if not widget:
        raise ValueError(f"Widget not found: {object_name}")

    if isinstance(widget, QComboBox):
        index = widget.findText(value)
        if index >= 0:
            widget.setCurrentIndex(index)
            return True
        raise ValueError(f"Value not found in combo: {value}")
    raise ValueError(f"Widget {object_name} is not a combo box")
```

## Testing Your Implementation

1. Start your app: `python main.py --port 9999`
2. Test connection:
```python
import socket, json
sock = socket.socket()
sock.connect(('localhost', 9999))
sock.send(b'{"type": "get_snapshot"}\n')
print(json.loads(sock.recv(4096)))
```

## Summary

To make any PyQt application testable via MCP:

1. Add `setObjectName()` to all interactive widgets
2. Copy the `CommandHandler`, `ControlServerHandler`, `ThreadedTCPServer`, and `run_control_server` code
3. Initialize the control server in your main function
4. Create an MCP server with tools that call the control protocol
5. Create `.mcp.json` in project root to register the MCP server
6. Create `.claude/settings.json` to allow the MCP tools

This enables Claude Code to fully interact with your desktop application just like Playwright MCP does with web browsers.

## Quick Start Checklist

```
your-project/
├── .mcp.json                    # MCP server configuration
├── .claude/
│   └── settings.json            # Allow mcp__pyqt-control tools
├── mcp_server/
│   └── pyqt_mcp.py              # MCP server (copy from this guide)
├── app/
│   └── main.py                  # Your PyQt app with control server
└── pyproject.toml               # Dependencies: PyQt6, mcp[cli]
```

Once configured, Claude Code can:
- `mcp__pyqt-control__launch_app` - Start the application
- `mcp__pyqt-control__get_snapshot` - See all UI elements
- `mcp__pyqt-control__click` - Click buttons/checkboxes
- `mcp__pyqt-control__fill` - Enter text in inputs
- `mcp__pyqt-control__get_text` - Read labels/values
- `mcp__pyqt-control__close_app` - Close the application
