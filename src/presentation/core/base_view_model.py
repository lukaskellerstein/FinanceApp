"""
Base ViewModel class with observable properties.

Provides reactive property binding using Qt signals.
"""

import logging
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar

from PyQt6.QtCore import QObject, pyqtSignal

log = logging.getLogger("CellarLogger")

T = TypeVar("T")


class ObservableProperty(Generic[T]):
    """
    Descriptor for observable properties in ViewModels.

    Automatically emits property_changed signal when value changes.

    Example:
        class MyViewModel(BaseViewModel):
            name = ObservableProperty[str]("")
            count = ObservableProperty[int](0)

        vm = MyViewModel()
        vm.name = "Test"  # Emits property_changed("name", "Test")
    """

    def __init__(self, default: T = None):
        self.default = default
        self.name: Optional[str] = None

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, obj: Optional[object], objtype: type = None) -> T:
        if obj is None:
            return self  # type: ignore
        return getattr(obj, f"_prop_{self.name}", self.default)

    def __set__(self, obj: object, value: T) -> None:
        old_value = getattr(obj, f"_prop_{self.name}", self.default)
        if old_value != value:
            setattr(obj, f"_prop_{self.name}", value)
            # Emit signal if available
            if hasattr(obj, "property_changed"):
                obj.property_changed.emit(self.name, value)


class BaseViewModel(QObject):
    """
    Base class for ViewModels in MVVM pattern.

    Features:
    - Observable properties via property_changed signal
    - Automatic cleanup on disposal
    - Error handling signal

    Example:
        class StocksViewModel(BaseViewModel):
            symbols = ObservableProperty[List[str]]([])
            selected_symbol = ObservableProperty[str]("")

            def __init__(self, watchlist_service: IWatchlistService):
                super().__init__()
                self._service = watchlist_service

            def load_watchlist(self):
                self.symbols = self._service.get_watchlist("STOCK")

        # In View:
        vm = StocksViewModel(service)
        vm.property_changed.connect(self._on_property_changed)
    """

    # Emitted when any property changes: (property_name, new_value)
    property_changed = pyqtSignal(str, object)

    # Emitted when an error occurs: (error_message)
    error_occurred = pyqtSignal(str)

    # Emitted when busy state changes
    is_busy_changed = pyqtSignal(bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_busy = False
        self._disposables: List[Any] = []

    @property
    def is_busy(self) -> bool:
        """Whether the ViewModel is currently busy (loading, etc.)."""
        return self._is_busy

    @is_busy.setter
    def is_busy(self, value: bool) -> None:
        if self._is_busy != value:
            self._is_busy = value
            self.is_busy_changed.emit(value)

    def set_property(self, name: str, value: Any) -> None:
        """
        Set a property value and emit change signal.

        Args:
            name: Property name
            value: New value
        """
        old_value = getattr(self, f"_prop_{name}", None)
        if old_value != value:
            setattr(self, f"_prop_{name}", value)
            self.property_changed.emit(name, value)

    def get_property(self, name: str, default: Any = None) -> Any:
        """
        Get a property value.

        Args:
            name: Property name
            default: Default value if not set

        Returns:
            Property value
        """
        return getattr(self, f"_prop_{name}", default)

    def add_disposable(self, disposable: Any) -> None:
        """
        Register a disposable for cleanup.

        Args:
            disposable: Object with dispose() method
        """
        self._disposables.append(disposable)

    def dispose(self) -> None:
        """Clean up all disposables."""
        for disposable in self._disposables:
            try:
                if hasattr(disposable, "dispose"):
                    disposable.dispose()
                elif hasattr(disposable, "disconnect"):
                    disposable.disconnect()
            except Exception as e:
                log.warning(f"Error disposing: {e}")
        self._disposables.clear()

    def handle_error(self, error: Exception) -> None:
        """
        Handle an error by emitting error_occurred signal.

        Args:
            error: The exception that occurred
        """
        error_msg = str(error)
        log.error(f"ViewModel error: {error_msg}")
        self.error_occurred.emit(error_msg)

    def __del__(self):
        """Cleanup on deletion."""
        self.dispose()
