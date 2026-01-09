"""
Application state store using Qt signals for reactive updates.

Replaces the RxPy BehaviorSubject-based state with a more efficient
Qt signal-based approach that's better integrated with PyQt6.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Generic, TypeVar, Optional, Callable, Any, List
from threading import Lock
import logging

from PyQt6.QtCore import QObject, pyqtSignal

from src.domain.value_objects.tick_data import TickData

log = logging.getLogger("CellarLogger")

T = TypeVar("T")


@dataclass
class AssetState:
    """
    State for a single asset in the store.

    Combines tick data with subscription status.
    """

    tick_data: TickData
    is_subscribed: bool = False
    last_updated: float = 0.0


class StateSlice(QObject, Generic[T]):
    """
    A typed slice of application state with Qt signal integration.

    Provides thread-safe state updates and change notifications through
    Qt signals. This replaces the RxPy BehaviorSubject pattern with
    native Qt mechanisms.

    Example:
        slice = StateSlice[AssetState]()
        slice.state_changed.connect(self.on_state_changed)

        slice.set("AAPL|AAPL", AssetState(tick_data=TickData(...)))
    """

    # Signal emitted when any state changes (emits the key that changed)
    state_changed = pyqtSignal(str)

    # Signal emitted when state is removed
    state_removed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._state: Dict[str, T] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[T]:
        """
        Get state for a key.

        Args:
            key: State key

        Returns:
            State value or None if not found
        """
        with self._lock:
            return self._state.get(key)

    def get_all(self) -> Dict[str, T]:
        """
        Get all state (returns copy).

        Returns:
            Copy of all state
        """
        with self._lock:
            return dict(self._state)

    def keys(self) -> List[str]:
        """
        Get all keys.

        Returns:
            List of keys
        """
        with self._lock:
            return list(self._state.keys())

    def set(self, key: str, value: T) -> None:
        """
        Set state for a key (thread-safe).

        Args:
            key: State key
            value: State value
        """
        with self._lock:
            self._state[key] = value
        # Emit signal outside lock
        self.state_changed.emit(key)

    def update(self, key: str, updater: Callable[[Optional[T]], T]) -> None:
        """
        Update state using an updater function (thread-safe).

        Args:
            key: State key
            updater: Function that takes current value and returns new value
        """
        with self._lock:
            current = self._state.get(key)
            self._state[key] = updater(current)
        self.state_changed.emit(key)

    def remove(self, key: str) -> Optional[T]:
        """
        Remove state for a key.

        Args:
            key: State key

        Returns:
            Removed value or None
        """
        with self._lock:
            value = self._state.pop(key, None)
        if value is not None:
            self.state_removed.emit(key)
        return value

    def contains(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: State key

        Returns:
            True if key exists
        """
        with self._lock:
            return key in self._state

    def clear(self) -> None:
        """Clear all state."""
        with self._lock:
            keys = list(self._state.keys())
            self._state.clear()
        for key in keys:
            self.state_removed.emit(key)

    def count(self) -> int:
        """
        Get number of items.

        Returns:
            Number of items in state
        """
        with self._lock:
            return len(self._state)


class AppStore(QObject):
    """
    Central application store.

    Singleton pattern with typed state slices. Replaces the old
    State singleton with a more structured approach.

    Example:
        store = AppStore.get_instance()
        store.stocks.set("AAPL|AAPL", AssetState(...))
        store.stocks.state_changed.connect(self.on_stock_changed)
    """

    _instance: Optional[AppStore] = None
    _initialized: bool = False

    # Global signals
    connection_status_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(str, str)  # (title, message)

    def __init__(self):
        # Skip if already initialized (singleton)
        if AppStore._initialized:
            return

        super().__init__()
        AppStore._initialized = True

        # State slices for different asset types
        self.stocks: StateSlice[AssetState] = StateSlice()
        self.futures: StateSlice[AssetState] = StateSlice()
        self.options: StateSlice[AssetState] = StateSlice()

        # UI state
        self.ui: StateSlice[Any] = StateSlice()

        # Connection state
        self._is_connected = False

        log.info("AppStore initialized")

    @classmethod
    def get_instance(cls) -> AppStore:
        """
        Get the singleton instance.

        Returns:
            The AppStore instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None
        cls._initialized = False

    def get_asset_slice(self, asset_type: str) -> StateSlice[AssetState]:
        """
        Get the appropriate state slice for an asset type.

        Args:
            asset_type: Type of asset ("STOCK", "FUTURE", "OPTION")

        Returns:
            StateSlice for the asset type

        Raises:
            ValueError: If unknown asset type
        """
        asset_type_upper = asset_type.upper()
        if asset_type_upper == "STOCK":
            return self.stocks
        elif asset_type_upper == "FUTURE":
            return self.futures
        elif asset_type_upper == "OPTION":
            return self.options
        raise ValueError(f"Unknown asset type: {asset_type}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        return self._is_connected

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        """Set connection status and emit signal."""
        if self._is_connected != value:
            self._is_connected = value
            self.connection_status_changed.emit(value)

    def report_error(self, title: str, message: str) -> None:
        """
        Report an error through the store.

        Args:
            title: Error title
            message: Error message
        """
        log.error(f"{title}: {message}")
        self.error_occurred.emit(title, message)
