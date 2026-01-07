# FinanceApp Refactoring Guide

This document describes the comprehensive refactoring plan for the FinanceApp PyQt6 financial trading application. It can be followed by developers or AI assistants to modernize the codebase while preserving all existing functionality.

## Table of Contents
1. [Current Architecture Analysis](#current-architecture-analysis)
2. [Target Architecture](#target-architecture)
3. [State Management Refactoring](#state-management-refactoring)
4. [Layer Architecture Refactoring](#layer-architecture-refactoring)
5. [UI Architecture Refactoring (MVVM)](#ui-architecture-refactoring-mvvm)
6. [Implementation Phases](#implementation-phases)
7. [File Mapping](#file-mapping)
8. [Code Examples](#code-examples)

---

## Current Architecture Analysis

### Current Structure
```
src/
├── ui/                    # UI Layer (PyQt6)
│   ├── base/              # BasePage with lifecycle
│   ├── state/             # Singleton state with RxPy BehaviorSubjects
│   ├── services/          # RealtimeDataService
│   ├── components/        # Charts, tables, inputs
│   └── windows/           # Main window + pages
├── business/              # Business Logic Layer
│   ├── modules/           # AssetBL, WatchlistBL (create their own dependencies)
│   ├── services/          # IBClient, ConfigService
│   ├── tasks/             # Download tasks with threading
│   └── model/             # Entities + Factories
└── db/                    # Database Layer
    ├── services/          # JsonAssetService, PyStoreHistService
    └── model/             # DBObject base
```

### Current Issues

1. **RxPy Overhead**: Each asset creates 17+ BehaviorSubject instances for real-time data
2. **Thread Safety**: RxPy callbacks from IB thread directly emit without proper marshalling
3. **Singleton Pattern**: State classes use singletons making testing difficult
4. **Hard-coded Dependencies**: Business modules instantiate their own dependencies
5. **Mixed Concerns**: UI services directly call business logic
6. **No Clear Interfaces**: Tight coupling between layers

### What Works Well (Preserve)
- Candlestick chart implementation (`src/ui/components/candlestick_chart/`)
- Watchlist table with drag-drop reordering
- HOF `setCurrentPage()` navigation pattern
- .ui file workflow with Qt Designer
- .qss stylesheet organization

---

## Target Architecture

### New Structure
```
src/
├── core/                           # Cross-cutting concerns
│   ├── interfaces/                 # Abstract interfaces
│   │   ├── broker.py              # IBrokerClient
│   │   ├── repositories.py        # IAssetRepository, etc.
│   │   └── services.py            # Business service interfaces
│   ├── di/                        # Dependency Injection
│   │   ├── container.py           # DI Container
│   │   └── providers.py           # Service registration
│   ├── config/
│   │   └── app_config.py          # Configuration management
│   ├── threading/
│   │   └── thread_manager.py      # Centralized thread management
│   └── exceptions/
│       └── exceptions.py          # Custom exceptions
│
├── domain/                         # Domain models
│   ├── entities/                   # Asset, Contract, Timeframe
│   └── value_objects/              # TickData, BarData (immutable)
│
├── infrastructure/                  # External integrations
│   ├── broker/                     # IB Client implementation
│   │   ├── ib_client.py
│   │   ├── ib_state.py            # Request state (extracted)
│   │   └── ib_mappers.py          # Type conversions
│   └── persistence/                # Repositories
│       ├── json/
│       ├── file/
│       └── pystore/
│
├── application/                    # Business services
│   ├── services/                   # AssetService, WatchlistService, etc.
│   └── tasks/                      # Background tasks
│
├── presentation/                   # UI Layer (renamed from ui/)
│   ├── core/                       # Base classes
│   │   ├── base_viewmodel.py
│   │   ├── base_view.py
│   │   └── base_window.py
│   ├── state/                      # App state (new architecture)
│   │   ├── store.py               # AppStore with StateSlice
│   │   └── market_data_bridge.py  # Thread-safe IB → UI
│   ├── components/                 # Reusable components
│   ├── windows/                    # Windows with MVVM
│   └── navigation/                 # Navigator, WindowManager
│
└── db/                             # Data storage (files only)
```

---

## State Management Refactoring

### Problem
Current RxPy-based state creates memory overhead and complexity:
- `RealtimeDataItem` has 17+ BehaviorSubjects per asset
- Manual subscription management prone to leaks
- Thread-unsafe callbacks from IB client

### Solution: Hybrid asyncio + Qt Signals

#### 1. TickData Dataclass (Immutable)
```python
# src/domain/value_objects/tick_data.py
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TickData:
    symbol: str
    local_symbol: str
    bid: float = 0.0
    bid_size: int = 0
    ask: float = 0.0
    ask_size: int = 0
    last: float = 0.0
    last_size: int = 0
    volume: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    timestamp: int = 0

    def with_update(self, field: str, value: Any) -> 'TickData':
        """Return new TickData with updated field."""
        return TickData(**{**self.__dict__, field: value})
```

#### 2. StateSlice with Qt Signals
```python
# src/presentation/state/store.py
from typing import Dict, Generic, TypeVar, Optional, Callable
from threading import Lock
from PyQt6.QtCore import QObject, pyqtSignal

T = TypeVar('T')

class StateSlice(QObject, Generic[T]):
    """Thread-safe state container with Qt signal notifications."""

    state_changed = pyqtSignal(str)  # Emits key that changed

    def __init__(self):
        super().__init__()
        self._state: Dict[str, T] = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[T]:
        with self._lock:
            return self._state.get(key)

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._state[key] = value
        self.state_changed.emit(key)

    def update(self, key: str, updater: Callable[[Optional[T]], T]) -> None:
        with self._lock:
            self._state[key] = updater(self._state.get(key))
        self.state_changed.emit(key)


class AppStore(QObject):
    """Central application store (singleton)."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        super().__init__()
        self._initialized = True
        self.stocks = StateSlice()
        self.futures = StateSlice()
```

#### 3. MarketDataBridge (Thread-Safe Queue)
```python
# src/presentation/state/market_data_bridge.py
from queue import Queue
from dataclasses import dataclass
from typing import Any
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

@dataclass
class MarketDataMessage:
    asset_type: str
    symbol: str
    local_symbol: str
    field: str
    value: Any
    timestamp: float

class MarketDataBridge(QObject):
    """Bridge IB client thread to Qt main thread via queue."""

    tick_received = pyqtSignal(str, str, str, object)

    def __init__(self):
        super().__init__()
        self._queue: Queue[MarketDataMessage] = Queue()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._process_queue)

    def start(self):
        self._timer.start(10)  # Process every 10ms

    def enqueue_tick(self, asset_type, symbol, local_symbol, field, value, timestamp):
        """Called from IB thread - thread-safe."""
        self._queue.put(MarketDataMessage(
            asset_type, symbol, local_symbol, field, value, timestamp
        ))

    def _process_queue(self):
        """Process queue in Qt main thread."""
        processed = 0
        while not self._queue.empty() and processed < 100:
            msg = self._queue.get_nowait()
            self.tick_received.emit(msg.asset_type, msg.symbol, msg.field, msg.value)
            processed += 1
```

### Migration Path
1. Create new state classes alongside existing
2. Update IB client to use bridge
3. Migrate pages one at a time to new store
4. Remove old RxPy state after all pages migrated

---

## Layer Architecture Refactoring

### Dependency Injection Container

```python
# src/core/di/container.py
from typing import Type, TypeVar, Dict, Optional, Callable, Any
import threading
import inspect

T = TypeVar('T')

class DIContainer:
    """Lightweight DI container with singleton/transient lifetimes."""

    def __init__(self):
        self._services: Dict[Type, dict] = {}
        self._singletons: Dict[Type, Any] = {}
        self._lock = threading.Lock()

    def register_singleton(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[['DIContainer'], T]] = None
    ):
        self._services[service_type] = {
            'impl': implementation,
            'factory': factory,
            'lifetime': 'singleton'
        }
        return self

    def register_transient(
        self,
        service_type: Type[T],
        implementation: Optional[Type[T]] = None
    ):
        self._services[service_type] = {
            'impl': implementation,
            'lifetime': 'transient'
        }
        return self

    def resolve(self, service_type: Type[T]) -> T:
        with self._lock:
            desc = self._services.get(service_type)
            if not desc:
                raise ValueError(f"Service {service_type} not registered")

            if desc['lifetime'] == 'singleton' and service_type in self._singletons:
                return self._singletons[service_type]

            instance = self._create_instance(desc)

            if desc['lifetime'] == 'singleton':
                self._singletons[service_type] = instance

            return instance

    def _create_instance(self, desc: dict) -> Any:
        if desc.get('factory'):
            return desc['factory'](self)

        impl_type = desc['impl']
        sig = inspect.signature(impl_type.__init__)
        kwargs = {}

        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            if param.annotation != inspect.Parameter.empty:
                try:
                    kwargs[name] = self.resolve(param.annotation)
                except ValueError:
                    if param.default == inspect.Parameter.empty:
                        raise

        return impl_type(**kwargs)
```

### Interface Definitions

```python
# src/core/interfaces/broker.py
from abc import ABC, abstractmethod
from typing import List, Observable
from datetime import datetime

class IBrokerClient(ABC):
    @abstractmethod
    def connect(self) -> None: pass

    @abstractmethod
    def disconnect(self) -> None: pass

    @abstractmethod
    def get_contract_details(self, contract) -> Observable: pass

    @abstractmethod
    def get_historical_data(self, contract, end_dt, duration, bar_size) -> Observable: pass

    @abstractmethod
    def subscribe_realtime(self, contract) -> Observable: pass

    @abstractmethod
    def unsubscribe_realtime(self, contract) -> None: pass


# src/core/interfaces/repositories.py
from abc import ABC, abstractmethod
from typing import List, Optional

class IAssetRepository(ABC):
    @abstractmethod
    def get(self, asset_type, symbol) -> Optional[dict]: pass

    @abstractmethod
    def get_all(self, asset_type) -> List[dict]: pass

    @abstractmethod
    def save(self, asset) -> None: pass

    @abstractmethod
    def delete(self, asset_type, symbol) -> None: pass


class IHistoricalDataRepository(ABC):
    @abstractmethod
    def get(self, symbol, timeframe) -> Optional[list]: pass

    @abstractmethod
    def save(self, symbol, timeframe, data) -> None: pass

    @abstractmethod
    def append(self, symbol, timeframe, data) -> None: pass


class IWatchlistRepository(ABC):
    @abstractmethod
    def get(self, watchlist_name) -> List[str]: pass

    @abstractmethod
    def update(self, watchlist_name, symbols) -> None: pass
```

### Service Registration

```python
# src/core/di/providers.py
def configure_services(container):
    """Configure all application services."""
    from src.core.config.app_config import AppConfig
    from src.core.threading.thread_manager import ThreadManager
    from src.infrastructure.broker.ib_client import IBClient
    from src.infrastructure.persistence.json.json_asset_repository import JsonAssetRepository
    from src.infrastructure.persistence.pystore.pystore_repository import PyStoreRepository
    from src.application.services.asset_service import AssetService
    from src.presentation.state.store import AppStore
    from src.presentation.state.market_data_bridge import MarketDataBridge

    # Core
    container.register_singleton(AppConfig)
    container.register_singleton(ThreadManager)
    container.register_singleton(MarketDataBridge)

    # Infrastructure
    container.register_singleton(IBrokerClient, implementation=IBClient)
    container.register_singleton(IAssetRepository, implementation=JsonAssetRepository)
    container.register_singleton(IHistoricalDataRepository, implementation=PyStoreRepository)

    # Application
    container.register_singleton(IAssetService, implementation=AssetService)

    # Presentation
    container.register_singleton(AppStore)

    return container
```

---

## UI Architecture Refactoring (MVVM)

### Base ViewModel

```python
# src/presentation/core/base_viewmodel.py
from typing import Dict, Callable, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal

class Command:
    """Command pattern for ViewModel actions."""
    def __init__(self, execute_fn, can_execute_fn=None):
        self._execute = execute_fn
        self._can_execute = can_execute_fn or (lambda: True)

    def execute(self, *args, **kwargs):
        if self.can_execute():
            return self._execute(*args, **kwargs)

    def can_execute(self) -> bool:
        return self._can_execute()


class BaseViewModel(QObject):
    """Base class for all ViewModels."""

    property_changed = pyqtSignal(str, object)  # (property_name, new_value)
    error_occurred = pyqtSignal(str, str)  # (title, message)

    def __init__(self):
        super().__init__()
        self._properties: Dict[str, Any] = {}
        self._commands: Dict[str, Command] = {}
        self._subscriptions = []

    def set_property(self, name: str, value: Any):
        old = self._properties.get(name)
        if old != value:
            self._properties[name] = value
            self.property_changed.emit(name, value)

    def get_property(self, name: str) -> Any:
        return self._properties.get(name)

    def create_command(self, name: str, execute_fn, can_execute_fn=None) -> Command:
        cmd = Command(execute_fn, can_execute_fn)
        self._commands[name] = cmd
        return cmd

    def initialize(self):
        """Override for async initialization."""
        pass

    def dispose(self):
        """Clean up subscriptions."""
        for sub in self._subscriptions:
            if hasattr(sub, 'dispose'):
                sub.dispose()
        self._subscriptions.clear()
```

### Base View

```python
# src/presentation/core/base_view.py
from typing import Optional, Type, TypeVar
from pathlib import Path
from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget

VM = TypeVar('VM', bound='BaseViewModel')

class BaseView(QWidget):
    """Base class for all Views (pages)."""

    on_update = pyqtSignal()  # Compatible with existing pattern

    # Override in subclasses
    ui_file: Optional[str] = None
    qss_file: Optional[str] = None
    viewmodel_class: Optional[Type[VM]] = None

    def __init__(self, viewmodel: Optional[VM] = None, **kwargs):
        super().__init__()
        self._viewmodel = None

        # Load UI
        if self.ui_file:
            uic.loadUi(self.ui_file, self)

        # Load styles
        if self.qss_file and Path(self.qss_file).exists():
            with open(self.qss_file) as f:
                self.setStyleSheet(f.read())

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Set ViewModel
        vm = viewmodel or (self.viewmodel_class(**kwargs) if self.viewmodel_class else None)
        if vm:
            self.set_viewmodel(vm)

    @property
    def viewmodel(self) -> Optional[VM]:
        return self._viewmodel

    def set_viewmodel(self, vm: VM):
        if self._viewmodel:
            self._viewmodel.dispose()
        self._viewmodel = vm
        self._viewmodel.error_occurred.connect(self._on_error)
        self.bind_viewmodel()
        self._viewmodel.initialize()

    def bind_viewmodel(self):
        """Override to create bindings."""
        pass

    def _on_error(self, title: str, message: str):
        """Handle ViewModel errors."""
        pass  # Override for custom handling

    def onDestroy(self):
        """Lifecycle method - compatible with existing pattern."""
        if self._viewmodel:
            self._viewmodel.dispose()
```

### Example: Stocks Watchlist MVVM

```python
# src/presentation/windows/main/pages/watchlists/stocks/viewmodel.py
from typing import Dict, List
from PyQt6.QtCore import pyqtSignal
from src.presentation.core.base_viewmodel import BaseViewModel
from src.core.interfaces.services import IWatchlistService, IRealtimeService

class StocksWatchlistViewModel(BaseViewModel):
    stock_updated = pyqtSignal(dict)
    stock_added = pyqtSignal(str)
    stock_removed = pyqtSignal(str)

    def __init__(self, watchlist_service: IWatchlistService, realtime_service: IRealtimeService):
        super().__init__()
        self._watchlist_service = watchlist_service
        self._realtime_service = realtime_service
        self._subscriptions_map: Dict[str, any] = {}

        # Properties
        self.set_property('is_loading', False)
        self.set_property('watchlist', [])

        # Commands
        self.add_command = self.create_command('add', self._add_stock)
        self.remove_command = self.create_command('remove', self._remove_stock)
        self.refresh_command = self.create_command('refresh', self._load_watchlist)

    def initialize(self):
        self._load_watchlist()

    def _load_watchlist(self):
        self.set_property('is_loading', True)
        try:
            symbols = self._watchlist_service.get_watchlist('stocks')
            self.set_property('watchlist', symbols)
            for symbol in symbols:
                self._subscribe_realtime(symbol)
        finally:
            self.set_property('is_loading', False)

    def _add_stock(self, ticker: str):
        ticker = ticker.upper().strip()
        if ticker:
            self._watchlist_service.add_to_watchlist('stocks', ticker)
            self._subscribe_realtime(ticker)
            self.stock_added.emit(ticker)

    def _remove_stock(self, ticker: str):
        self._unsubscribe_realtime(ticker)
        self._watchlist_service.remove_from_watchlist('stocks', ticker)
        self.stock_removed.emit(ticker)

    def _subscribe_realtime(self, ticker: str):
        observable = self._realtime_service.subscribe('STOCK', ticker)
        sub = observable.subscribe(lambda tick: self.stock_updated.emit(tick))
        self._subscriptions_map[ticker] = sub

    def _unsubscribe_realtime(self, ticker: str):
        if ticker in self._subscriptions_map:
            self._subscriptions_map[ticker].dispose()
            del self._subscriptions_map[ticker]
        self._realtime_service.unsubscribe('STOCK', ticker)

    def dispose(self):
        for sub in self._subscriptions_map.values():
            sub.dispose()
        self._subscriptions_map.clear()
        super().dispose()


# src/presentation/windows/main/pages/watchlists/stocks/view.py
from src.presentation.core.base_view import BaseView
from .viewmodel import StocksWatchlistViewModel
from src.presentation.components.tables.stock_table import StockTable

class StocksWatchlistView(BaseView):
    ui_file = "src/presentation/windows/main/pages/watchlists/stocks/stocks_page.ui"
    qss_file = "src/presentation/windows/main/pages/watchlists/stocks/stocks_page.qss"
    viewmodel_class = StocksWatchlistViewModel

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.table = StockTable()
        self.tableBox1.addWidget(self.table)

    def bind_viewmodel(self):
        vm = self.viewmodel

        # Button → Command
        self.startRealtime1Button.clicked.connect(
            lambda: vm.add_command.execute(self.ticker1Input.text())
        )
        self.loadSavedLayoutButton.clicked.connect(vm.refresh_command.execute)

        # ViewModel signals → View
        vm.stock_updated.connect(self.table.model.on_tick_update)
        vm.stock_removed.connect(self.table.model.remove_row)

        # Table signals → ViewModel
        self.table.on_remove.connect(lambda row: vm.remove_command.execute(row.name))
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Files to Create)
```
src/core/
├── __init__.py
├── interfaces/
│   ├── __init__.py
│   ├── broker.py
│   ├── repositories.py
│   └── services.py
├── di/
│   ├── __init__.py
│   ├── container.py
│   └── providers.py
├── config/
│   ├── __init__.py
│   └── app_config.py
├── threading/
│   ├── __init__.py
│   └── thread_manager.py
└── exceptions/
    ├── __init__.py
    └── exceptions.py
```

### Phase 2: State Management (Files to Create)
```
src/presentation/state/
├── __init__.py
├── store.py              # AppStore, StateSlice
└── market_data_bridge.py # Thread-safe queue bridge

src/domain/value_objects/
├── __init__.py
├── tick_data.py
└── bar_data.py
```

### Phase 3: Domain Layer (Files to Create)
```
src/domain/
├── __init__.py
├── entities/
│   ├── __init__.py
│   ├── asset.py          # Copy from business/model/asset.py
│   ├── contract.py       # Decoupled from ibapi
│   └── timeframe.py      # Copy from business/model/timeframe.py
└── value_objects/
    └── (created in Phase 2)
```

### Phase 4: Infrastructure Layer (Files to Create/Move)
```
src/infrastructure/
├── __init__.py
├── broker/
│   ├── __init__.py
│   ├── ib_client.py      # Refactored from business/services/ibclient/
│   ├── ib_state.py       # Extracted state management
│   └── ib_mappers.py     # Type conversion
└── persistence/
    ├── __init__.py
    ├── json/
    │   └── json_asset_repository.py    # From db/services/json_asset_service.py
    ├── file/
    │   └── file_watchlist_repository.py # From db/services/file_watchlist_service.py
    └── pystore/
        └── pystore_repository.py        # From db/services/pystore_hist_service.py
```

### Phase 5: Application Layer (Files to Create/Move)
```
src/application/
├── __init__.py
├── services/
│   ├── __init__.py
│   ├── asset_service.py      # From business/modules/asset_bl.py
│   ├── watchlist_service.py  # From business/modules/*_watchlist_bl.py
│   └── realtime_service.py   # From ui/services/realtime_data_service.py
└── tasks/
    ├── __init__.py
    └── download_task.py      # From business/tasks/
```

### Phase 6: Presentation Layer (Files to Create)
```
src/presentation/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── base_viewmodel.py
│   ├── base_view.py
│   └── base_window.py
├── navigation/
│   ├── __init__.py
│   ├── navigator.py
│   └── window_manager.py
└── (move existing ui/ contents here)
```

### Phase 7: Integration
1. Update `main.py` to use DI container
2. Wire up all services
3. Remove old code after verification

---

## File Mapping

| Old File | New Location | Action |
|----------|--------------|--------|
| `src/ui/state/main.py` | `src/presentation/state/store.py` | Replace |
| `src/ui/state/realtime_data.py` | `src/presentation/state/market_data_bridge.py` | Replace |
| `src/business/services/ibclient/my_ib_client.py` | `src/infrastructure/broker/ib_client.py` | Refactor |
| `src/business/services/ibclient/state.py` | `src/infrastructure/broker/ib_state.py` | Extract |
| `src/business/modules/asset_bl.py` | `src/application/services/asset_service.py` | Refactor |
| `src/business/modules/*_watchlist_bl.py` | `src/application/services/watchlist_service.py` | Merge |
| `src/db/services/json_asset_service.py` | `src/infrastructure/persistence/json/` | Move |
| `src/db/services/pystore_hist_service.py` | `src/infrastructure/persistence/pystore/` | Move |
| `src/ui/services/realtime_data_service.py` | `src/application/services/realtime_service.py` | Move |
| `src/ui/base/base_page.py` | `src/presentation/core/base_view.py` | Enhance |
| `src/ui/windows/*` | `src/presentation/windows/*` | Move + MVVM |
| `src/ui/components/*` | `src/presentation/components/*` | Move (charts preserved) |
| `src/business/model/*` | `src/domain/entities/*` | Move |

---

## Code Examples

### Modified IB Client with Bridge

```python
# src/infrastructure/broker/ib_client.py
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.ticktype import TickTypeEnum

class IBClient(EWrapper, EClient):
    def __init__(self, config, thread_manager, bridge):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        self._config = config
        self._thread_manager = thread_manager
        self._bridge = bridge  # MarketDataBridge
        self._state = IBRequestState()

    def connect(self):
        cfg = self._config.broker_config
        self._thread_manager.register_thread(
            f"IBClient-{id(self)}",
            lambda: (super().connect(cfg.ip, cfg.port, cfg.client_id), self.run()),
            auto_start=True
        )

    # Tick callbacks use bridge (thread-safe)
    def tickPrice(self, reqId, tickType, price, attrib):
        info = self._state.get_subscription_info(reqId)
        if info:
            self._bridge.enqueue_tick(
                info['asset_type'],
                info['symbol'],
                info['local_symbol'],
                TickTypeEnum.to_str(tickType).lower(),
                price,
                time.time()
            )
```

### Efficient Table Model

```python
# src/presentation/components/tables/stock_table/model.py
from PyQt6.QtCore import QAbstractTableModel, Qt, pyqtSlot
import pandas as pd

class StockTableModel(QAbstractTableModel):
    COLUMNS = ['symbol', 'bid', 'ask', 'last', 'volume', 'change']

    def __init__(self):
        super().__init__()
        self._data = pd.DataFrame(columns=self.COLUMNS)

    @pyqtSlot(dict)
    def on_tick_update(self, tick: dict):
        """Efficient cell-level update."""
        ticker = tick.get('ticker')
        field = tick.get('type')
        value = tick.get('price')

        if ticker not in self._data.index:
            self._add_row(ticker)

        if field in self._data.columns:
            self._data.loc[ticker, field] = value
            row = self._data.index.get_loc(ticker)
            col = self._data.columns.get_loc(field)
            idx = self.createIndex(row, col)
            self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

    def _add_row(self, ticker):
        row = len(self._data)
        self.beginInsertRows(self.createIndex(-1, -1), row, row)
        self._data.loc[ticker] = [ticker, 0, 0, 0, 0, 0]
        self.endInsertRows()
```

### Application Entry Point

```python
# src/main.py
import sys
from PyQt6.QtWidgets import QApplication
from src.core.di.container import DIContainer
from src.core.di.providers import configure_services
from src.core.interfaces.broker import IBrokerClient
from src.core.threading.thread_manager import ThreadManager
from src.presentation.state.market_data_bridge import MarketDataBridge
from src.presentation.windows.main.view import MainWindow

def main():
    # Create and configure DI container
    container = DIContainer()
    configure_services(container)

    # Start services
    bridge = container.resolve(MarketDataBridge)
    bridge.start()

    broker = container.resolve(IBrokerClient)
    broker.connect()

    # Create Qt app
    app = QApplication(sys.argv)

    # Create main window with container
    window = MainWindow(container=container)
    window.show()

    exit_code = app.exec()

    # Cleanup
    container.resolve(ThreadManager).shutdown()
    broker.disconnect()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
```

---

## Verification Checklist

After each phase, verify:

- [ ] Application starts without errors
- [ ] Watchlists load saved symbols
- [ ] Real-time data updates appear in tables
- [ ] Charts render correctly
- [ ] Asset detail windows open
- [ ] No memory leaks (monitor with profiler)
- [ ] Thread safety (no race conditions)

Final verification:
- [ ] All unit tests pass
- [ ] All existing functionality works
- [ ] Performance matches or exceeds original
- [ ] Code is testable (can mock dependencies)

---

## Resources

- [PyQt6 Tutorial](https://www.pythonguis.com/pyqt6-tutorial/)
- [MVVM Pattern for PyQt](https://medium.com/@mark_huber/a-clean-architecture-for-a-pyqt-gui-using-the-mvvm-pattern-b8e5d9ae833d)
- [aioreactive](https://github.com/dbrattli/aioreactive) - If full async reactive is needed later
- [Qt Material Stylesheet](https://github.com/UN-GCPDS/qt-material) - Optional styling upgrade
