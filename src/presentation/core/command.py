"""
Command classes for MVVM pattern.

Provides bindable commands with can_execute checking.
"""

import logging
import threading
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger("CellarLogger")


class Command(QObject):
    """
    Bindable command for MVVM pattern.

    Wraps a function with can_execute checking and execution notification.

    Example:
        class MyViewModel(BaseViewModel):
            def __init__(self):
                super().__init__()
                self.save_command = Command(
                    execute=self._save,
                    can_execute=lambda: self.has_changes,
                )

            def _save(self):
                # Save logic here
                pass

        # In View:
        self.save_button.clicked.connect(vm.save_command.execute)
        vm.save_command.can_execute_changed.connect(
            self.save_button.setEnabled
        )
    """

    # Emitted when can_execute state changes
    can_execute_changed = pyqtSignal(bool)

    # Emitted before execution
    executing = pyqtSignal()

    # Emitted after execution
    executed = pyqtSignal()

    def __init__(
        self,
        execute: Callable[..., Any],
        can_execute: Optional[Callable[[], bool]] = None,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize command.

        Args:
            execute: Function to execute
            can_execute: Optional function returning whether command can execute
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._execute = execute
        self._can_execute = can_execute or (lambda: True)
        self._last_can_execute = True

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """
        Execute the command if can_execute returns True.

        Args:
            *args: Arguments to pass to execute function
            **kwargs: Keyword arguments to pass to execute function

        Returns:
            Result of execute function or None if cannot execute
        """
        if not self.can_execute():
            log.debug("Command cannot execute")
            return None

        self.executing.emit()
        try:
            result = self._execute(*args, **kwargs)
            return result
        finally:
            self.executed.emit()

    def can_execute(self) -> bool:
        """
        Check if command can execute.

        Returns:
            True if command can execute
        """
        return self._can_execute()

    def raise_can_execute_changed(self) -> None:
        """
        Notify that can_execute state may have changed.

        Call this when conditions affecting can_execute have changed.
        """
        current = self.can_execute()
        if current != self._last_can_execute:
            self._last_can_execute = current
            self.can_execute_changed.emit(current)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow calling command directly."""
        return self.execute(*args, **kwargs)


class AsyncCommand(QObject):
    """
    Async command that executes in a background thread.

    Prevents multiple concurrent executions and provides progress notification.

    Example:
        class MyViewModel(BaseViewModel):
            def __init__(self):
                super().__init__()
                self.download_command = AsyncCommand(
                    execute=self._download,
                    can_execute=lambda: not self.is_busy,
                )

            def _download(self, progress_callback):
                for i in range(100):
                    # Do work...
                    progress_callback(i)

        # In View:
        vm.download_command.progress.connect(self.progress_bar.setValue)
        vm.download_command.completed.connect(self._on_download_complete)
    """

    # Emitted when can_execute state changes
    can_execute_changed = pyqtSignal(bool)

    # Emitted with progress (0-100)
    progress = pyqtSignal(int)

    # Emitted before execution starts
    started = pyqtSignal()

    # Emitted after execution completes (with result)
    completed = pyqtSignal(object)

    # Emitted if execution fails (with error message)
    failed = pyqtSignal(str)

    def __init__(
        self,
        execute: Callable[..., Any],
        can_execute: Optional[Callable[[], bool]] = None,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize async command.

        Args:
            execute: Function to execute (receives progress_callback as first arg)
            can_execute: Optional function returning whether command can execute
            parent: Optional parent QObject
        """
        super().__init__(parent)
        self._execute = execute
        self._can_execute = can_execute or (lambda: True)
        self._is_running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        """Check if command is currently running."""
        return self._is_running

    def execute(self, *args: Any, **kwargs: Any) -> bool:
        """
        Execute the command asynchronously.

        Args:
            *args: Arguments to pass to execute function
            **kwargs: Keyword arguments to pass to execute function

        Returns:
            True if execution started, False if cannot execute
        """
        if not self.can_execute() or self._is_running:
            return False

        self._is_running = True
        self.started.emit()
        self.can_execute_changed.emit(False)

        def run():
            try:
                result = self._execute(self._report_progress, *args, **kwargs)
                self.completed.emit(result)
            except Exception as e:
                log.error(f"AsyncCommand failed: {e}")
                self.failed.emit(str(e))
            finally:
                self._is_running = False
                self.can_execute_changed.emit(self._can_execute())

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return True

    def _report_progress(self, value: int) -> None:
        """Report progress (called from execute function)."""
        self.progress.emit(value)

    def can_execute(self) -> bool:
        """
        Check if command can execute.

        Returns:
            True if command can execute and not currently running
        """
        return self._can_execute() and not self._is_running

    def cancel(self) -> None:
        """
        Request cancellation.

        Note: The execute function must check for cancellation.
        """
        # Cancellation would require cooperative checking in execute function
        log.debug("Cancellation requested")

    def __call__(self, *args: Any, **kwargs: Any) -> bool:
        """Allow calling command directly."""
        return self.execute(*args, **kwargs)
