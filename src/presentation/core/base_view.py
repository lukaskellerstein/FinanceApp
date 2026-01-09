"""
Base View class with automatic UI loading.

Provides automatic .ui and .qss file loading based on class name.
"""

import logging
import os
from typing import Any, Dict, Optional, Tuple, Type, TypeVar

from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from src.presentation.core.base_view_model import BaseViewModel

log = logging.getLogger("CellarLogger")

VM = TypeVar("VM", bound=BaseViewModel)


class BaseView(QWidget):
    """
    Base class for Views in MVVM pattern.

    Features:
    - Automatic .ui file loading based on class location
    - Automatic .qss stylesheet loading
    - ViewModel binding support
    - Lifecycle management (onDestroy)

    Usage:
        1. Place .ui and .qss files next to the view class
        2. Name them same as the Python file (e.g., stocks_page.py -> stocks_page.ui)
        3. Inherit from BaseView and implement bind_view_model()

    Example:
        class StocksPage(BaseView[StocksViewModel]):
            def __init__(self):
                super().__init__()
                self.set_view_model(StocksViewModel())

            def bind_view_model(self, vm: StocksViewModel):
                vm.property_changed.connect(self._on_property_changed)
                vm.symbols_changed.connect(self._update_table)
    """

    # Signal for update notifications
    on_update = pyqtSignal()

    # Override in subclass to specify UI/QSS paths
    ui_file: Optional[str] = None
    qss_file: Optional[str] = None

    def __init__(
        self,
        *args: Tuple[str, Any],
        **kwargs: Dict[str, Any],
    ):
        super().__init__(*args, **kwargs)
        self._view_model: Optional[BaseViewModel] = None
        self._connections: list = []

        # Load UI and styles
        self._load_ui()
        self._load_styles()

        log.debug(f"{self.__class__.__name__} initialized")

    def _get_file_path(self, extension: str) -> Optional[str]:
        """
        Get the path to a companion file (.ui or .qss).

        Args:
            extension: File extension (e.g., ".ui")

        Returns:
            Full path to file or None if not found
        """
        # Get the module file path
        import inspect
        module = inspect.getmodule(self.__class__)
        if module is None or module.__file__ is None:
            return None

        module_dir = os.path.dirname(module.__file__)
        module_name = os.path.splitext(os.path.basename(module.__file__))[0]

        # Try the same directory
        file_path = os.path.join(module_dir, f"{module_name}{extension}")
        if os.path.exists(file_path):
            return file_path

        return None

    def _load_ui(self) -> None:
        """Load the .ui file if it exists."""
        ui_path = self.ui_file or self._get_file_path(".ui")
        if ui_path and os.path.exists(ui_path):
            try:
                uic.loadUi(ui_path, self)
                log.debug(f"Loaded UI: {ui_path}")
            except Exception as e:
                log.error(f"Error loading UI {ui_path}: {e}")

    def _load_styles(self) -> None:
        """Load the .qss file if it exists."""
        qss_path = self.qss_file or self._get_file_path(".qss")
        if qss_path and os.path.exists(qss_path):
            try:
                with open(qss_path, "r") as f:
                    self.setStyleSheet(f.read())
                log.debug(f"Loaded styles: {qss_path}")
            except Exception as e:
                log.error(f"Error loading styles {qss_path}: {e}")

    @property
    def view_model(self) -> Optional[BaseViewModel]:
        """Get the bound ViewModel."""
        return self._view_model

    def set_view_model(self, view_model: BaseViewModel) -> None:
        """
        Set and bind the ViewModel.

        Args:
            view_model: The ViewModel to bind
        """
        # Unbind previous if exists
        if self._view_model is not None:
            self._unbind_view_model()

        self._view_model = view_model

        # Bind the new ViewModel
        self._bind_view_model(view_model)
        self.bind_view_model(view_model)

    def _bind_view_model(self, vm: BaseViewModel) -> None:
        """
        Internal binding setup.

        Args:
            vm: The ViewModel to bind
        """
        # Connect error handling
        conn = vm.error_occurred.connect(self._on_error)
        self._connections.append(conn)

        # Connect busy state
        conn = vm.is_busy_changed.connect(self._on_busy_changed)
        self._connections.append(conn)

    def bind_view_model(self, vm: BaseViewModel) -> None:
        """
        Override this to bind ViewModel properties to View elements.

        Args:
            vm: The ViewModel to bind
        """
        pass  # Override in subclass

    def _unbind_view_model(self) -> None:
        """Unbind the current ViewModel."""
        for conn in self._connections:
            try:
                if conn:
                    self._view_model.disconnect(conn)
            except (TypeError, RuntimeError):
                pass
        self._connections.clear()

        if self._view_model:
            self._view_model.dispose()

    def _on_error(self, error_msg: str) -> None:
        """
        Handle error from ViewModel.

        Args:
            error_msg: Error message
        """
        log.error(f"View error: {error_msg}")
        # Override to show error dialog, etc.

    def _on_busy_changed(self, is_busy: bool) -> None:
        """
        Handle busy state change.

        Args:
            is_busy: Whether ViewModel is busy
        """
        # Override to show loading indicator, etc.
        pass

    def onDestroy(self) -> None:
        """
        Called when view is being destroyed.

        Override to add custom cleanup logic.
        """
        log.debug(f"{self.__class__.__name__} destroying")
        self._unbind_view_model()

    def __del__(self):
        """Python destructor."""
        log.debug(f"{self.__class__.__name__} deleted")
