"""
Control Server for PyQt6 Application Testability via MCP.

This module provides a TCP control server that allows external tools (like Claude Code
via MCP) to inspect and interact with the PyQt6 application for testing purposes.

Usage:
    from src.ui.control_server import CommandHandler, run_control_server

    # In your main function, after creating the main window:
    command_handler = CommandHandler(window)
    control_server = run_control_server(command_handler, host="localhost", port=9999)
"""

import json
import logging
import threading
import socketserver
from typing import Optional, Any, Dict, List

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QLabel,
    QCheckBox,
    QListWidget,
    QTableWidget,
    QTableView,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QTextEdit,
    QPlainTextEdit,
    QRadioButton,
    QTabWidget,
    QStackedWidget,
    QTreeWidget,
    QTreeView,
    QSlider,
    QProgressBar,
    QMenuBar,
    QMenu,
    QApplication,
    QMainWindow,
)

log = logging.getLogger("CellarLogger")


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
            log.error(f"Control server command error: {e}")
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
        elif cmd_type == "select_combo":
            return self._select_combo(command.get("object_name"), command.get("value"))
        elif cmd_type == "get_combo_items":
            return self._get_combo_items(command.get("object_name"))
        elif cmd_type == "select_tab":
            return self._select_tab(command.get("object_name"), command.get("index"))
        elif cmd_type == "get_table_data":
            return self._get_table_data(command.get("object_name"))
        elif cmd_type == "click_table_cell":
            return self._click_table_cell(
                command.get("object_name"),
                command.get("row"),
                command.get("column"),
                command.get("double_click", False)
            )
        elif cmd_type == "trigger_action":
            return self._trigger_action(command.get("object_name"))
        elif cmd_type == "get_window_info":
            return self._get_window_info()
        elif cmd_type == "close":
            QTimer.singleShot(100, self.app.close)
            return True
        else:
            raise ValueError(f"Unknown command type: {cmd_type}")

    def _get_snapshot(self) -> Dict:
        """Get a snapshot of all widgets in the application and other windows."""
        widgets = []
        all_windows = []

        def collect_widgets(widget: QWidget, parent_path: str = ""):
            obj_name = widget.objectName()
            widget_path = f"{parent_path}/{obj_name}" if parent_path else obj_name

            if obj_name and not obj_name.startswith("qt_"):  # Skip internal Qt widgets
                widget_info = {
                    "object_name": obj_name,
                    "path": widget_path,
                    "type": widget.__class__.__name__,
                    "visible": widget.isVisible(),
                    "enabled": widget.isEnabled(),
                }

                # Add type-specific info
                if isinstance(widget, QLineEdit):
                    widget_info["text"] = widget.text()
                    widget_info["placeholder"] = widget.placeholderText()
                    widget_info["readonly"] = widget.isReadOnly()
                elif isinstance(widget, QPushButton):
                    widget_info["text"] = widget.text()
                    widget_info["checkable"] = widget.isCheckable()
                    if widget.isCheckable():
                        widget_info["checked"] = widget.isChecked()
                elif isinstance(widget, QLabel):
                    widget_info["text"] = widget.text()
                elif isinstance(widget, QCheckBox):
                    widget_info["checked"] = widget.isChecked()
                    widget_info["text"] = widget.text()
                elif isinstance(widget, QRadioButton):
                    widget_info["checked"] = widget.isChecked()
                    widget_info["text"] = widget.text()
                elif isinstance(widget, QComboBox):
                    widget_info["current_text"] = widget.currentText()
                    widget_info["current_index"] = widget.currentIndex()
                    widget_info["count"] = widget.count()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    widget_info["value"] = widget.value()
                    widget_info["minimum"] = widget.minimum()
                    widget_info["maximum"] = widget.maximum()
                elif isinstance(widget, QTextEdit):
                    widget_info["text"] = widget.toPlainText()
                elif isinstance(widget, QPlainTextEdit):
                    widget_info["text"] = widget.toPlainText()
                elif isinstance(widget, QListWidget):
                    widget_info["count"] = widget.count()
                    widget_info["current_row"] = widget.currentRow()
                elif isinstance(widget, QTableWidget):
                    widget_info["row_count"] = widget.rowCount()
                    widget_info["column_count"] = widget.columnCount()
                elif isinstance(widget, QTableView):
                    model = widget.model()
                    if model:
                        try:
                            # Some models require a parent index
                            from PyQt6.QtCore import QModelIndex
                            widget_info["row_count"] = model.rowCount(QModelIndex())
                            widget_info["column_count"] = model.columnCount(QModelIndex())
                        except TypeError:
                            # Fall back to no-arg version
                            widget_info["row_count"] = model.rowCount()
                            widget_info["column_count"] = model.columnCount()
                elif isinstance(widget, QTabWidget):
                    widget_info["current_index"] = widget.currentIndex()
                    widget_info["count"] = widget.count()
                    widget_info["tab_texts"] = [widget.tabText(i) for i in range(widget.count())]
                elif isinstance(widget, QStackedWidget):
                    widget_info["current_index"] = widget.currentIndex()
                    widget_info["count"] = widget.count()
                elif isinstance(widget, QSlider):
                    widget_info["value"] = widget.value()
                    widget_info["minimum"] = widget.minimum()
                    widget_info["maximum"] = widget.maximum()
                elif isinstance(widget, QProgressBar):
                    widget_info["value"] = widget.value()
                    widget_info["minimum"] = widget.minimum()
                    widget_info["maximum"] = widget.maximum()

                widgets.append(widget_info)

            for child in widget.children():
                if isinstance(child, QWidget):
                    collect_widgets(child, widget_path)

        # Collect from main window
        collect_widgets(self.app)
        all_windows.append({
            "title": self.app.windowTitle(),
            "size": {"width": self.app.width(), "height": self.app.height()},
            "is_main": True
        })

        # Collect from all other top-level windows
        app = QApplication.instance()
        if app:
            for window in app.topLevelWidgets():
                if window != self.app and isinstance(window, QMainWindow) and window.isVisible():
                    collect_widgets(window)
                    all_windows.append({
                        "title": window.windowTitle(),
                        "size": {"width": window.width(), "height": window.height()},
                        "is_main": False
                    })

        # Also collect menu actions from all windows
        menu_actions = self._collect_menu_actions()

        return {
            "window_title": self.app.windowTitle(),
            "window_size": {"width": self.app.width(), "height": self.app.height()},
            "windows": all_windows,
            "widgets": widgets,
            "menu_actions": menu_actions
        }

    def _collect_menu_actions(self) -> List[Dict]:
        """Collect all menu actions from all windows' menu bars."""
        actions = []

        def collect_from_window(window: QWidget):
            menu_bar = window.findChild(QMenuBar)
            if menu_bar:
                for menu_action in menu_bar.actions():
                    menu = menu_action.menu()
                    if menu:
                        for action in menu.actions():
                            if action.objectName() and not action.isSeparator():
                                actions.append({
                                    "object_name": action.objectName(),
                                    "text": action.text().replace("&", ""),
                                    "enabled": action.isEnabled(),
                                    "checked": action.isChecked() if action.isCheckable() else None,
                                    "menu": menu.title().replace("&", ""),
                                    "window": window.windowTitle()
                                })

        # Collect from main window
        collect_from_window(self.app)

        # Collect from all other top-level windows
        app = QApplication.instance()
        if app:
            for window in app.topLevelWidgets():
                if window != self.app and isinstance(window, QMainWindow) and window.isVisible():
                    collect_from_window(window)

        return actions

    def _find_widget(self, object_name: str) -> Optional[QWidget]:
        """Find a widget by its object name across all windows."""
        # First try the main window
        widget = self.app.findChild(QWidget, object_name)
        if widget:
            return widget

        # Search in all top-level windows
        app = QApplication.instance()
        if app:
            for window in app.topLevelWidgets():
                if window != self.app:
                    widget = window.findChild(QWidget, object_name)
                    if widget:
                        return widget
        return None

    def _find_action(self, object_name: str) -> Optional[QAction]:
        """Find a QAction by its object name across all windows."""
        # First try the main window
        action = self.app.findChild(QAction, object_name)
        if action:
            return action

        # Search in all top-level windows
        app = QApplication.instance()
        if app:
            for window in app.topLevelWidgets():
                if window != self.app:
                    action = window.findChild(QAction, object_name)
                    if action:
                        return action
        return None

    def _click(self, object_name: str) -> bool:
        """Click on a widget."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, (QPushButton, QCheckBox, QRadioButton)):
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
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
            widget.setPlainText(text)
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
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
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
        elif isinstance(widget, (QCheckBox, QRadioButton)):
            return widget.text()
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
            return widget.toPlainText()
        elif isinstance(widget, QComboBox):
            return widget.currentText()
        else:
            raise ValueError(f"Widget {object_name} does not have text")

    def _get_checkbox_state(self, object_name: str) -> bool:
        """Get the state of a checkbox."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, (QCheckBox, QRadioButton)):
            return widget.isChecked()
        else:
            raise ValueError(f"Widget {object_name} is not a checkbox")

    def _set_checkbox(self, object_name: str, checked: bool) -> bool:
        """Set the state of a checkbox."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, (QCheckBox, QRadioButton)):
            widget.setChecked(checked)
            return True
        else:
            raise ValueError(f"Widget {object_name} is not a checkbox")

    def _select_combo(self, object_name: str, value: str) -> bool:
        """Select a value in a combo box."""
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

    def _get_combo_items(self, object_name: str) -> List[str]:
        """Get all items in a combo box."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QComboBox):
            return [widget.itemText(i) for i in range(widget.count())]
        raise ValueError(f"Widget {object_name} is not a combo box")

    def _select_tab(self, object_name: str, index: int) -> bool:
        """Select a tab in a tab widget."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QTabWidget):
            if 0 <= index < widget.count():
                widget.setCurrentIndex(index)
                return True
            raise ValueError(f"Tab index out of range: {index}")
        raise ValueError(f"Widget {object_name} is not a tab widget")

    def _get_table_data(self, object_name: str) -> Dict:
        """Get data from a table widget."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QTableWidget):
            rows = []
            for row in range(widget.rowCount()):
                row_data = []
                for col in range(widget.columnCount()):
                    item = widget.item(row, col)
                    row_data.append(item.text() if item else "")
                rows.append(row_data)

            headers = []
            for col in range(widget.columnCount()):
                header = widget.horizontalHeaderItem(col)
                headers.append(header.text() if header else f"Column {col}")

            return {
                "headers": headers,
                "rows": rows,
                "row_count": widget.rowCount(),
                "column_count": widget.columnCount()
            }
        elif isinstance(widget, QTableView):
            model = widget.model()
            if model:
                from PyQt6.QtCore import QModelIndex
                parent_index = QModelIndex()
                rows = []
                row_count = model.rowCount(parent_index)
                col_count = model.columnCount(parent_index)
                for row in range(row_count):
                    row_data = []
                    for col in range(col_count):
                        index = model.index(row, col, parent_index)
                        row_data.append(str(model.data(index) or ""))
                    rows.append(row_data)

                headers = []
                for col in range(col_count):
                    headers.append(str(model.headerData(col, 1) or f"Column {col}"))  # 1 = Horizontal

                return {
                    "headers": headers,
                    "rows": rows,
                    "row_count": row_count,
                    "column_count": col_count
                }
        raise ValueError(f"Widget {object_name} is not a table")

    def _click_table_cell(self, object_name: str, row: int, column: int, double_click: bool = False) -> bool:
        """Click on a table cell."""
        widget = self._find_widget(object_name)
        if not widget:
            raise ValueError(f"Widget not found: {object_name}")

        if isinstance(widget, QTableWidget):
            if 0 <= row < widget.rowCount() and 0 <= column < widget.columnCount():
                widget.setCurrentCell(row, column)
                if double_click:
                    widget.cellDoubleClicked.emit(row, column)
                else:
                    widget.cellClicked.emit(row, column)
                return True
            raise ValueError(f"Cell ({row}, {column}) out of range")
        elif isinstance(widget, QTableView):
            model = widget.model()
            if model:
                from PyQt6.QtCore import QModelIndex
                parent_index = QModelIndex()
                if 0 <= row < model.rowCount(parent_index) and 0 <= column < model.columnCount(parent_index):
                    index = model.index(row, column, parent_index)
                    widget.setCurrentIndex(index)
                    if double_click:
                        widget.doubleClicked.emit(index)
                    else:
                        widget.clicked.emit(index)
                    return True
            raise ValueError(f"Cell ({row}, {column}) out of range")
        raise ValueError(f"Widget {object_name} is not a table")

    def _trigger_action(self, object_name: str) -> bool:
        """Trigger a menu action by its object name."""
        action = self._find_action(object_name)
        if not action:
            raise ValueError(f"Action not found: {object_name}")

        if action.isEnabled():
            action.trigger()
            return True
        raise ValueError(f"Action {object_name} is not enabled")

    def _get_window_info(self) -> Dict:
        """Get window information."""
        return {
            "title": self.app.windowTitle(),
            "width": self.app.width(),
            "height": self.app.height(),
            "x": self.app.x(),
            "y": self.app.y(),
            "minimized": self.app.isMinimized(),
            "maximized": self.app.isMaximized(),
            "visible": self.app.isVisible(),
        }


class ControlServerHandler(socketserver.StreamRequestHandler):
    """Handler for control server connections."""

    def handle(self):
        """Handle incoming connections."""
        log.info(f"Control server: New connection from {self.client_address}")
        while True:
            try:
                line = self.rfile.readline()
                if not line:
                    break

                command = json.loads(line.decode('utf-8'))
                log.debug(f"Control server received command: {command.get('type')}")

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

            except json.JSONDecodeError as e:
                log.error(f"Control server JSON decode error: {e}")
                error_response = json.dumps({"status": "error", "message": f"Invalid JSON: {e}"}) + "\n"
                self.wfile.write(error_response.encode('utf-8'))
                self.wfile.flush()
            except Exception as e:
                log.error(f"Control server error: {e}")
                error_response = json.dumps({"status": "error", "message": str(e)}) + "\n"
                self.wfile.write(error_response.encode('utf-8'))
                self.wfile.flush()
                break


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Threaded TCP server for handling control connections."""
    allow_reuse_address = True
    daemon_threads = True


def run_control_server(
    command_handler: CommandHandler,
    host: str = "localhost",
    port: int = 9999
) -> ThreadedTCPServer:
    """
    Run the control server in a separate thread.

    Args:
        command_handler: The CommandHandler instance connected to the main window
        host: Host address to bind to (default: localhost)
        port: Port to bind to (default: 9999)

    Returns:
        The ThreadedTCPServer instance
    """
    server = ThreadedTCPServer((host, port), ControlServerHandler)
    server.command_handler = command_handler

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    log.info(f"Control server running on {host}:{port}")
    return server
