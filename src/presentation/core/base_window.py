"""
Base Window class with automatic UI loading.

Provides automatic .ui and .qss file loading for windows.
"""

import logging
import os
from typing import Any, Callable, Dict, Optional, Tuple, Type

from PyQt6 import uic
from PyQt6.QtWidgets import QMainWindow

from src.presentation.core.base_view import BaseView
from src.presentation.core.base_view_model import BaseViewModel

log = logging.getLogger("CellarLogger")


class BaseWindow(QMainWindow):
    """
    Base class for Windows in MVVM pattern.

    Features:
    - Automatic .ui file loading based on class location
    - Automatic .qss stylesheet loading
    - Page navigation with setCurrentPage HOF pattern
    - Lifecycle management

    Example:
        class MainWindow(BaseWindow):
            def __init__(self):
                super().__init__()
                self.setObjectName("main_window")

                # Setup navigation
                self.actionHome.triggered.connect(
                    self.setCurrentPage(HomePage)
                )

        # The setCurrentPage pattern is preserved from original code
    """

    # Override in subclass to specify UI/QSS paths
    ui_file: Optional[str] = None
    qss_file: Optional[str] = None

    def __init__(
        self,
        *args: Tuple[str, Any],
        **kwargs: Dict[str, Any],
    ):
        super().__init__(*args, **kwargs)
        self._current_page: Optional[BaseView] = None
        self._view_model: Optional[BaseViewModel] = None

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
        import inspect
        module = inspect.getmodule(self.__class__)
        if module is None or module.__file__ is None:
            return None

        module_dir = os.path.dirname(module.__file__)
        module_name = os.path.splitext(os.path.basename(module.__file__))[0]

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
    def current_page(self) -> Optional[BaseView]:
        """Get the current page."""
        return self._current_page

    def setCurrentPage(
        self,
        page_class: Type[BaseView],
        **kwargs: Any,
    ) -> Callable[[], None]:
        """
        Higher-Order Function for page navigation.

        Returns a function that switches to the specified page.
        This pattern allows use with Qt signal connections:

            self.actionHome.triggered.connect(self.setCurrentPage(HomePage))

        Args:
            page_class: The page class to instantiate
            **kwargs: Arguments to pass to page constructor

        Returns:
            Function that performs the page switch
        """

        def set_page() -> None:
            # Destroy current page
            if self._current_page is not None:
                if hasattr(self, "pageBox"):
                    self.pageBox.removeWidget(self._current_page)
                self._current_page.onDestroy()

            # Create new page
            if kwargs:
                self._current_page = page_class(**kwargs)
            else:
                self._current_page = page_class()

            # Add to container
            if hasattr(self, "pageBox"):
                self.pageBox.addWidget(self._current_page)
                self.pageBox.setCurrentIndex(0)

        return set_page

    def set_view_model(self, view_model: BaseViewModel) -> None:
        """
        Set the window's ViewModel.

        Args:
            view_model: The ViewModel to bind
        """
        if self._view_model is not None:
            self._view_model.dispose()

        self._view_model = view_model
        self.bind_view_model(view_model)

    def bind_view_model(self, vm: BaseViewModel) -> None:
        """
        Override to bind ViewModel to window elements.

        Args:
            vm: The ViewModel to bind
        """
        pass  # Override in subclass

    def closeEvent(self, event: Any) -> None:
        """Handle window close event."""
        log.info(f"{self.__class__.__name__} closing")

        # Destroy current page
        if self._current_page is not None:
            self._current_page.onDestroy()

        # Dispose ViewModel
        if self._view_model is not None:
            self._view_model.dispose()

        event.accept()

    def __del__(self):
        """Python destructor."""
        log.debug(f"{self.__class__.__name__} deleted")
