# MCP Application Launch with Regolith/i3 Workspace Management

This document describes how to implement automatic workspace allocation for PyQt6 applications launched via MCP (Model Context Protocol), specifically designed for Regolith Linux (i3wm-based).

## Problem Statement

When running multiple Claude Code terminals, each needs to launch and control its own instance of the application. By default:
1. Applications open on the currently active monitor/workspace
2. Multiple instances would conflict on the same port
3. Window titles don't distinguish between instances
4. Moving windows with `[title="..."] move` steals focus

## Solution Overview

Implement workspace-aware application launching that:
1. **Allocates dedicated workspaces** (100-120 range) for each instance
2. **Auto-assigns unique ports** based on workspace number (10100-10120)
3. **Sets unique window titles** with workspace ID (e.g., "App Name [100]")
4. **Moves windows using con_id** (no focus stealing)

## Architecture

```
Claude Code Terminal ──MCP Protocol──> MCP Server ──TCP──> PyQt Application
     (Workspace 35)      (stdio)      (pyqt_mcp.py)        (Workspace 100)
                                           │
                                           ├─ 1. Find available workspace (100-120)
                                           ├─ 2. Launch app on current workspace
                                           ├─ 3. Get window's con_id from i3 tree
                                           ├─ 4. Move container by con_id (no focus steal)
                                           └─ 5. Return workspace/port info
```

## Implementation

### Prerequisites

- Regolith Linux or any i3wm-based desktop
- `i3-msg` command available
- MCP server for PyQt application control

### Files to Modify

1. `mcp_server/pyqt_mcp.py` - MCP server with workspace management
2. `main.py` - CLI argument parsing
3. `src/ui/main_window.py` - Dynamic window title

---

### 1. MCP Server (`mcp_server/pyqt_mcp.py`)

Add these helper functions after imports:

```python
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
```

Modify `launch_app()` function:

```python
@mcp.tool()
def launch_app(app_path: str = "", host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, wait_time: float = 3.0) -> Dict[str, Any]:
    """
    Launch the application on a dedicated workspace.

    Args:
        app_path: Path to the application's main.py file
        host: Control server host (default: localhost)
        port: Control server port - if 9999 (default), auto-assigns based on workspace (10100-10120)
        wait_time: Seconds to wait for app to start (default: 3.0)

    Returns:
        Dict with status, message, window_title, workspace, and port on success
    """
    global _app_process

    if not app_path:
        app_path = APP_PATH

    if not app_path or not os.path.exists(app_path):
        return {"status": "error", "message": f"Application not found: {app_path}"}

    try:
        # Find available workspace in range 100-120
        target_workspace = _get_available_workspace(100, 120)
        if target_workspace is None:
            return {"status": "error", "message": "No available workspace in range 100-120"}

        # Auto-assign port if using default (workspace 100 = port 10100)
        actual_port = port
        if port == DEFAULT_PORT:
            actual_port = 10000 + target_workspace  # e.g., 10100, 10101, ...

        # Use workspace number as client_id to avoid IB connection conflicts
        client_id = target_workspace

        # Launch app (opens on current workspace initially)
        cmd = [sys.executable, app_path, "--host", host, "--port", str(actual_port),
               "--workspace", str(target_workspace), "--client-id", str(client_id)]
        _app_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        time.sleep(wait_time)

        if _app_process.poll() is not None:
            stdout, stderr = _app_process.communicate()
            return {"status": "error", "message": f"App failed to start: {stderr.decode()}"}

        response = _send_command({"type": "get_snapshot"}, host, actual_port)
        window_title = response.get("result", {}).get("window_title")

        # Move window to dedicated workspace using con_id (no focus steal)
        if window_title:
            con_id = _get_window_con_id(window_title)
            if con_id:
                _move_container_to_workspace(con_id, target_workspace)

        return {
            "status": "success",
            "message": f"Application launched on workspace {target_workspace} (port {actual_port})",
            "window_title": window_title,
            "workspace": target_workspace,
            "port": actual_port
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

---

### 2. Main Entry Point (`main.py`)

Add CLI arguments and auto-detection functions:

```python
import socket
from pathlib import Path

def _is_port_available(port: int, host: str = "localhost") -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False

def _find_available_port(start: int = 9999, end: int = 10099, host: str = "localhost") -> int:
    """Find an available port in the given range."""
    for port in range(start, end + 1):
        if _is_port_available(port, host):
            return port
    raise RuntimeError(f"No available port found in range {start}-{end}")

def _get_used_client_ids() -> set:
    """Get client IDs currently in use by checking lock files."""
    lock_dir = Path("/tmp/options_trading_locks")
    used_ids = set()
    if lock_dir.exists():
        for lock_file in lock_dir.glob("client_*.lock"):
            try:
                pid = int(lock_file.read_text().strip())
                if Path(f"/proc/{pid}").exists():
                    client_id = int(lock_file.stem.split("_")[1])
                    used_ids.add(client_id)
                else:
                    lock_file.unlink()  # Clean up stale lock
            except (ValueError, FileNotFoundError):
                pass
    return used_ids

def _find_available_client_id(start: int = 1, end: int = 99) -> int:
    """Find an available client ID in the given range."""
    used_ids = _get_used_client_ids()
    for client_id in range(start, end + 1):
        if client_id not in used_ids:
            return client_id
    raise RuntimeError(f"No available client ID found in range {start}-{end}")

def _register_client_id(client_id: int) -> None:
    """Register a client ID as in use by creating a lock file."""
    lock_dir = Path("/tmp/options_trading_locks")
    lock_dir.mkdir(exist_ok=True)
    lock_file = lock_dir / f"client_{client_id}.lock"
    lock_file.write_text(str(os.getpid()))
```

CLI arguments:

```python
parser.add_argument("--port", type=int, default=None, help="Control server port (auto-detect if not specified)")
parser.add_argument("--client-id", type=int, default=None, help="IB client ID (auto-detect if not specified)")
parser.add_argument("--workspace", type=int, default=None, help="Workspace ID for window title")
```

Auto-detection and registration:

```python
# Auto-detect client_id (range 1-99 for manual, 100-120 for MCP)
if args.client_id is not None:
    client_id = args.client_id
else:
    client_id = _find_available_client_id(start=1, end=99)

_register_client_id(client_id)

# Override IB client_id in config
config._config["ib_connection"]["client_id"] = client_id

# Auto-detect port (range 9999-10099 for manual, 10100-10120 for MCP)
if args.port is not None:
    control_port = args.port
else:
    control_port = _find_available_port(start=9999, end=10099)
```

Terminal output banner:

```python
print("\n" + "=" * 60)
print("  OPTIONS TRADING PLATFORM - Started")
print("=" * 60)
print(f"  IB Client ID:    {client_id}")
print(f"  Control Port:    {control_port if control_port else 'disabled'}")
print(f"  Workspace:       {args.workspace if args.workspace else 'default'}")
print("=" * 60 + "\n")
```

---

### 3. Main Window (`src/ui/main_window.py`)

Add import:

```python
from typing import Optional
```

Modify `__init__`:

```python
def __init__(self, workspace_id: Optional[int] = None):
    super().__init__()
    self.workspace_id = workspace_id
    # ... rest of init
```

Set dynamic window title in `_init_ui()`:

```python
def _init_ui(self) -> None:
    if self.workspace_id:
        self.setWindowTitle(f"Your App Name [{self.workspace_id}]")
    else:
        self.setWindowTitle("Your App Name")
    # ... rest of UI init
```

---

## Why con_id Instead of Workspace Switching?

The original approach (switch workspace → launch → switch back) had issues:
- Brief focus flicker during workspace switches
- Potential race conditions with fast operations

The con_id approach (same as Regolith's `move-to-workspace.sh`):
- Launches app on current workspace
- Finds window's container ID from i3 tree
- Uses `[con_id=X] move container to workspace number Y`
- **No focus change** - terminal stays focused

This is the same technique used by Regolith's built-in workspace management scripts.

---

## Port and Client ID Assignment

### Automatic Allocation Ranges

| Launch Method | Port Range | Client ID Range |
|---------------|------------|-----------------|
| Manual start  | 9999-10099 | 1-99            |
| MCP launch    | 10100-10120| 100-120         |

### MCP-Launched Instances

| Workspace | Port  | IB Client ID |
|-----------|-------|--------------|
| 100       | 10100 | 100          |
| 101       | 10101 | 101          |
| ...       | ...   | ...          |
| 120       | 10120 | 120          |

### Manual Starts (Auto-Detection)

When you run `python main.py` without explicit `--port` or `--client-id`:
- **Port**: Auto-detects first available port in 9999-10099
- **Client ID**: Auto-detects first available client_id in 1-99 (uses lock files in `/tmp/options_trading_locks/`)

**Terminal Output**: On startup, the app displays a banner showing assigned values:

```
============================================================
  OPTIONS TRADING PLATFORM - Started
============================================================
  IB Client ID:    1
  Control Port:    9999
  Workspace:       default
============================================================
```

This allows multiple manual instances to coexist:
```bash
# Terminal 1: Auto-assigns port=9999, client_id=1
python main.py

# Terminal 2: Auto-assigns port=10000, client_id=2
python main.py

# Terminal 3: Explicit values
python main.py --port 10050 --client-id 50
```

**Why different client IDs?** IB TWS/Gateway only allows ONE connection per client_id. Each instance needs a unique client_id to connect simultaneously.

---

## Usage

### Launch from Claude Code

```
mcp__pyqt-control__launch_app()
```

**Returns:**
```json
{
  "status": "success",
  "message": "Application launched on workspace 100 (port 10100)",
  "window_title": "Your App Name [100]",
  "workspace": 100,
  "port": 10100
}
```

### Verify Workspace

```bash
i3-msg -t get_workspaces | python3 -c "import json,sys; print([w['num'] for w in json.load(sys.stdin) if w['num']>=100])"
```

### Verify Focus (should stay on terminal workspace)

```bash
i3-msg -t get_workspaces | python3 -c "import json,sys; ws=json.load(sys.stdin); print('Focused:', [w['num'] for w in ws if w['focused']])"
```

### Control Application

**Automatic Port Tracking**: After `launch_app()`, the MCP server remembers the assigned port. All subsequent tool calls automatically use that port - no need to pass it explicitly:

```
# Launch returns port 10100
mcp__pyqt-control__launch_app()

# These automatically use port 10100 (no port parameter needed!)
mcp__pyqt-control__get_snapshot()
mcp__pyqt-control__click(object_name="my_button")
mcp__pyqt-control__select_tab(object_name="main_tabs", index=1)
mcp__pyqt-control__close_app()
```

**Explicit Port Override**: You can still pass an explicit port if needed (e.g., to control your manually-started main app on port 9999):

```
mcp__pyqt-control__get_snapshot(port=9999)  # Controls main app
mcp__pyqt-control__click(object_name="my_button", port=10100)  # Controls launched instance
```

---

## Multi-Instance Scenario

**Terminal 1** (workspace 35):
```
> launch_app()
→ Opens "App [100]" on workspace 100, port 10100
→ Focus stays on workspace 35
```

**Terminal 2** (workspace 22):
```
> launch_app()
→ Opens "App [101]" on workspace 101, port 10101
→ Focus stays on workspace 22
```

Each instance is independently controllable via its assigned port.

---

## Behavior Summary

| Feature | Behavior |
|---------|----------|
| Workspace range | 100-120 (21 concurrent MCP instances) |
| MCP port assignment | Automatic: 10000 + workspace_num |
| MCP client ID | Automatic: workspace_num (avoids conflicts) |
| Manual port assignment | Auto-detect in 9999-10099 |
| Manual client ID | Auto-detect in 1-99 (lock files in /tmp) |
| Port tracking | **Automatic** - remembered after MCP launch |
| Window title | "App Name [workspace_id]" |
| Focus after launch | **Stays on original workspace** (no steal) |
| Workspace detection | Checks if workspace EXISTS (any windows) |
| Move method | `[con_id=X] move container` (Regolith-style) |

---

## Port Tracking Implementation

The MCP server tracks the launched instance's port to avoid conflicts with manually-running applications:

```python
_launched_port: Optional[int] = None  # Track port of launched instance

def _get_effective_port(port: int) -> int:
    """Get the effective port - use launched port if available and default was passed."""
    global _launched_port
    if port == DEFAULT_PORT and _launched_port is not None:
        return _launched_port
    return port
```

**How it works:**
1. `launch_app()` stores the assigned port in `_launched_port`
2. All other tools call `_get_effective_port(port)` before sending commands
3. If no explicit port is passed (default 9999), uses tracked port
4. If explicit port is passed, uses that instead
5. `close_app()` clears `_launched_port` when closing the launched instance

**Why this matters:**
- User's manually-started main app runs on port 9999
- MCP-launched test instance runs on port 10100
- Without tracking, tools would default to 9999 and control the wrong app
- With tracking, tools automatically target the test instance

---

## Child Windows / Dialogs

For dialogs and child windows to open on the same workspace as the main window, ensure Qt widgets have proper parent set:

```python
# Bad - dialog may open on wrong workspace
QMessageBox.information(None, "Title", "Message")

# Good - dialog follows parent window
QMessageBox.information(self, "Title", "Message")
```

i3 keeps transient windows (dialogs with parent) on the same workspace as their parent.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| "No available workspace in range 100-120" | All 21 workspaces occupied | Close unused instances |
| "Application not found" | Invalid app_path | Set PYQT_APP_PATH env var |
| Connection refused | App not started | Increase wait_time |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PYQT_APP_PATH` | Path to main.py | (none) |
| `PYQT_CONTROL_HOST` | Control server host | localhost |
| `PYQT_CONTROL_PORT` | Default port (triggers auto-assign) | 9999 |

---

## Non-Regolith Systems

On systems without i3wm, the workspace functions will fail gracefully:
- `_get_available_workspace()` returns fallback value
- `_get_window_con_id()` returns `None` → no move attempted
- App still launches and is controllable, just on current workspace

To support non-i3 systems, the implementation already handles missing i3-msg gracefully.
