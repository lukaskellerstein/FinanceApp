import argparse
import logging
import logging.config
import signal
import sys
import os

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.ui.windows.main.main_window import MainWindow
from src.ui.control_server import CommandHandler, run_control_server

# Change to the project root directory so relative UI paths work
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# set logging from config file
logging.config.fileConfig("./src/logging.conf")

# create logger
log = logging.getLogger("CellarLogger")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Finance App")
    parser.add_argument(
        "--port",
        type=int,
        default=19999,
        help="Control server port (default: 19999)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Control server host (default: localhost)"
    )
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Disable control server for MCP testability"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        app = QApplication(sys.argv)
        app.setStartDragDistance(1)  # pixels
        app.setStartDragTime(1)  # ms

        # Allow Ctrl+C to properly terminate the application
        signal.signal(signal.SIGINT, lambda *args: app.quit())
        # Timer lets Python process signals while Qt event loop runs
        timer = QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(100)

        window = MainWindow()
        window.show()

        # Start control server for MCP testability (unless disabled)
        control_server = None
        if not args.no_server:
            command_handler = CommandHandler(window)
            control_server = run_control_server(
                command_handler,
                host=args.host,
                port=args.port
            )
            log.info(f"MCP control server started on {args.host}:{args.port}")

        sys.exit(app.exec())
    except Exception as e:
        log.fatal(e)
    except:
        log.fatal("Something else went wrong")
