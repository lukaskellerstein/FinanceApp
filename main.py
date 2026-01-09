"""
FinanceApp - Main entry point.

Uses the new Clean Architecture with:
- Dependency Injection
- MVVM pattern for UI
- MCP control server for testability
"""

import argparse
import logging
import logging.config
import signal
import socket
import sys
import os
import threading
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# Track Ctrl+C presses for force quit
_ctrl_c_count = 0
_shutdown_watchdog = None

# Change to the project root directory so relative paths work
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# =============================================================================
# Auto-Detection Functions for Multi-Instance Support
# =============================================================================

def _is_port_available(port: int, host: str = "localhost") -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def _find_available_port(start: int = 29999, end: int = 30099, host: str = "localhost") -> int:
    """Find an available port in the given range."""
    for port in range(start, end + 1):
        if _is_port_available(port, host):
            return port
    raise RuntimeError(f"No available port found in range {start}-{end}")


def _get_used_client_ids() -> set:
    """Get client IDs currently in use by checking lock files."""
    lock_dir = Path("/tmp/finance_app_locks")
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
    lock_dir = Path("/tmp/finance_app_locks")
    lock_dir.mkdir(exist_ok=True)
    lock_file = lock_dir / f"client_{client_id}.lock"
    lock_file.write_text(str(os.getpid()))

# Set logging from config file
logging.config.fileConfig("./src/logging.conf")

# Create logger
log = logging.getLogger("CellarLogger")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Finance App")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Control server port (auto-detect if not specified)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Control server host (default: localhost)"
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=None,
        help="IB client ID (auto-detect if not specified)"
    )
    parser.add_argument(
        "--workspace",
        type=int,
        default=None,
        help="Workspace ID for window title (used by MCP for multi-instance support)"
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Disable control server for MCP testability"
    )
    parser.add_argument(
        "--no-ib",
        action="store_true",
        help="Don't connect to Interactive Brokers"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        # =================================================================
        # Auto-detect client_id and port for multi-instance support
        # =================================================================

        # Auto-detect client_id (range 1-99 for manual, 100-120 for MCP)
        if args.client_id is not None:
            client_id = args.client_id
        else:
            client_id = _find_available_client_id(start=1, end=99)

        _register_client_id(client_id)

        # Auto-detect port (range 29999-30099 for manual, 10100-10120 for MCP)
        if args.port is not None:
            control_port = args.port
        else:
            control_port = _find_available_port(start=29999, end=30099)

        # =================================================================
        # Print startup banner
        # =================================================================
        print("\n" + "=" * 60)
        print("  FINANCE APP - Started")
        print("=" * 60)
        print(f"  IB Client ID:    {client_id}")
        print(f"  Control Port:    {control_port if not args.no_server else 'disabled'}")
        print(f"  Workspace:       {args.workspace if args.workspace else 'default'}")
        print("=" * 60 + "\n")

        # Initialize Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("FinanceApp")
        app.setStartDragDistance(1)  # pixels
        app.setStartDragTime(1)  # ms

        # Watchdog thread that forces exit after timeout
        def shutdown_watchdog(timeout_seconds):
            """Force exit if graceful shutdown takes too long."""
            import time
            time.sleep(timeout_seconds)
            print(f"\nShutdown timeout ({timeout_seconds}s) - forcing exit!", flush=True)
            os._exit(1)

        # Allow Ctrl+C to properly terminate the application
        def handle_sigint(signum, frame):
            global _ctrl_c_count, _shutdown_watchdog
            _ctrl_c_count += 1
            if _ctrl_c_count == 1:
                print("\nCtrl+C pressed, shutting down (press again to force)...", flush=True)
                # Start watchdog thread - force exit after 3 seconds
                _shutdown_watchdog = threading.Thread(
                    target=shutdown_watchdog, args=(3,), daemon=True
                )
                _shutdown_watchdog.start()
                app.quit()
            else:
                # Force exit immediately - don't wait for anything
                print("\nForce exit!", flush=True)
                os._exit(1)

        signal.signal(signal.SIGINT, handle_sigint)
        signal.signal(signal.SIGTERM, handle_sigint)

        # Timer lets Python process signals while Qt event loop runs
        timer = QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(50)  # More frequent to catch signals faster

        # Initialize application bootstrap with DI
        from src.application.bootstrap import initialize_app
        bootstrap = initialize_app()

        # Override IB client_id in config
        from src.core.config import AppConfig
        app_config = AppConfig()
        if "IB" not in app_config._config:
            app_config._config["IB"] = {}
        app_config._config["IB"]["client_id"] = str(client_id)

        # Start IB connection (unless disabled)
        if not args.no_ib:
            bootstrap.start()

        # Create main window using new MVVM architecture
        from src.presentation.windows import MainWindow
        window = MainWindow(workspace_id=args.workspace)
        window.show()

        # Start control server for MCP testability (unless disabled)
        control_server = None
        if not args.no_server:
            from src.infrastructure.control_server import CommandHandler, run_control_server
            command_handler = CommandHandler(window)
            control_server = run_control_server(
                command_handler,
                host=args.host,
                port=control_port
            )
            log.info(f"MCP control server started on {args.host}:{control_port}")

        sys.exit(app.exec())

    except Exception as e:
        log.fatal(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
