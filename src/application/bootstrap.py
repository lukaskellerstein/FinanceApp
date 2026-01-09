"""
Application bootstrap and dependency injection configuration.

Configures and wires up all services with their dependencies.
"""

import logging
import threading
from typing import Optional

from src.core.di.container import DIContainer
from src.core.config.app_config import AppConfig
from src.core.interfaces.broker import IBrokerClient
from src.core.interfaces.repositories import (
    IAssetRepository,
    IHistoricalDataRepository,
    IWatchlistRepository,
)
from src.core.interfaces.services import (
    IAssetService,
    IWatchlistService,
    IHistoricalDataService,
    IRealtimeService,
)

from src.infrastructure.broker import IBClient, IBState
from src.infrastructure.persistence import (
    JsonAssetRepository,
    PyStoreHistoricalRepository,
    FileWatchlistRepository,
)

from src.application.services import (
    AssetService,
    WatchlistService,
    HistoricalDataService,
    RealtimeService,
)

from src.presentation.state.market_data_bridge import MarketDataBridge

log = logging.getLogger("CellarLogger")


class ApplicationBootstrap:
    """
    Application bootstrapper.

    Configures dependency injection container and starts services.

    Example:
        bootstrap = ApplicationBootstrap()
        bootstrap.configure()
        bootstrap.start()

        # Get services
        asset_service = bootstrap.asset_service

        # Cleanup on exit
        bootstrap.shutdown()
    """

    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize bootstrap.

        Args:
            config: Optional application configuration
        """
        self.config = config or AppConfig()
        self.container = DIContainer()
        self._ib_thread: Optional[threading.Thread] = None
        self._configured = False
        self._started = False

    def configure(self) -> None:
        """Configure all dependencies in the container."""
        if self._configured:
            return

        log.info("Configuring application dependencies")

        # Register configuration
        self.container.register_singleton(
            AppConfig,
            instance=self.config,
        )

        # Register infrastructure layer
        self._register_infrastructure()

        # Register application layer
        self._register_services()

        self._configured = True
        log.info("Application dependencies configured")

    def _register_infrastructure(self) -> None:
        """Register infrastructure layer dependencies."""
        config = self.config
        db_config = config.database_config

        # Market data bridge (singleton for thread-safe communication)
        self.container.register_singleton(MarketDataBridge)

        # IB State (singleton)
        self.container.register_singleton(IBState)

        # Asset repository
        self.container.register_singleton(
            IAssetRepository,
            factory=lambda c: JsonAssetRepository(db_config.assets_path),
        )

        # Historical data repository
        self.container.register_singleton(
            IHistoricalDataRepository,
            factory=lambda c: PyStoreHistoricalRepository(
                db_config.historical_data_path,
                "cellarstone_db",
            ),
        )

        # Watchlist repository
        self.container.register_singleton(
            IWatchlistRepository,
            factory=lambda c: FileWatchlistRepository(db_config.watchlists_path),
        )

        # Broker client (needs bridge and state)
        def create_broker(c: DIContainer):
            bridge = c.resolve(MarketDataBridge)
            state = c.resolve(IBState)
            return IBClient(bridge, self.config, state)

        self.container.register_singleton(
            IBrokerClient,
            factory=create_broker,
        )

    def _register_services(self) -> None:
        """Register application layer services."""

        # Asset service
        def create_asset_service(c: DIContainer):
            repo = c.resolve(IAssetRepository)
            broker = c.resolve(IBrokerClient)
            return AssetService(repo, broker)

        self.container.register_singleton(
            IAssetService,
            factory=create_asset_service,
        )

        # Watchlist service
        def create_watchlist_service(c: DIContainer):
            repo = c.resolve(IWatchlistRepository)
            asset_service = c.resolve(IAssetService)
            return WatchlistService(repo, asset_service)

        self.container.register_singleton(
            IWatchlistService,
            factory=create_watchlist_service,
        )

        # Historical data service
        def create_historical_service(c: DIContainer):
            repo = c.resolve(IHistoricalDataRepository)
            broker = c.resolve(IBrokerClient)
            return HistoricalDataService(repo, broker)

        self.container.register_singleton(
            IHistoricalDataService,
            factory=create_historical_service,
        )

        # Realtime service
        def create_realtime_service(c: DIContainer):
            broker = c.resolve(IBrokerClient)
            bridge = c.resolve(MarketDataBridge)
            asset_service = c.resolve(IAssetService)
            return RealtimeService(broker, bridge, asset_service)

        self.container.register_singleton(
            IRealtimeService,
            factory=create_realtime_service,
        )

    def start(self) -> None:
        """Start the application (connect to IB)."""
        if not self._configured:
            self.configure()

        if self._started:
            return

        log.info("Starting application")

        # Start IB client in background thread
        self._ib_thread = threading.Thread(
            name="IB-Client-Thread",
            target=self._run_ib_client,
            daemon=True,
        )
        self._ib_thread.start()

        self._started = True
        log.info("Application started")

    def _run_ib_client(self) -> None:
        """Run IB client message loop."""
        broker = None
        try:
            broker = self.container.resolve(IBrokerClient)
            broker.connect()
            broker.start()  # Blocking message loop
        except Exception as e:
            log.error(f"IB client error: {e}")
        finally:
            # If we exit without connection being established, mark as error
            if broker is not None:
                from src.infrastructure.broker import ConnectionState
                if hasattr(broker, '_connection_state'):
                    if broker._connection_state == ConnectionState.CONNECTING:
                        broker._connection_state = ConnectionState.ERROR
                        broker._connection_error = "Connection failed - IB thread exited"
                        broker._connected_event.set()  # Unblock waiters
                        log.warning("IB client thread exited without connecting")

    def shutdown(self) -> None:
        """Shutdown the application."""
        log.info("Shutting down application")

        # Disconnect broker (only if we started it)
        try:
            if self._started and self.container.is_registered(IBrokerClient):
                log.debug("Disconnecting broker...")
                broker = self.container.resolve(IBrokerClient)
                if broker.is_connected():
                    broker.disconnect()
                log.debug("Broker disconnected")
        except Exception as e:
            log.warning(f"Error disconnecting broker: {e}")

        # Stop market data bridge
        try:
            if self.container.is_registered(MarketDataBridge):
                log.debug("Stopping market data bridge...")
                bridge = self.container.resolve(MarketDataBridge)
                bridge.stop()
                log.debug("Market data bridge stopped")
        except Exception as e:
            log.warning(f"Error stopping market data bridge: {e}")

        # Dispose all services (with protection against blocking)
        try:
            log.debug("Disposing services...")
            self.container.dispose_all()
            log.debug("Services disposed")
        except Exception as e:
            log.warning(f"Error disposing services: {e}")

        self._started = False
        log.info("Application shutdown complete")

    # ----------------------------------------------------------------
    # Convenience accessors
    # ----------------------------------------------------------------

    @property
    def asset_service(self) -> IAssetService:
        """Get asset service."""
        return self.container.resolve(IAssetService)

    @property
    def watchlist_service(self) -> IWatchlistService:
        """Get watchlist service."""
        return self.container.resolve(IWatchlistService)

    @property
    def historical_data_service(self) -> IHistoricalDataService:
        """Get historical data service."""
        return self.container.resolve(IHistoricalDataService)

    @property
    def realtime_service(self) -> IRealtimeService:
        """Get realtime service."""
        return self.container.resolve(IRealtimeService)

    @property
    def market_data_bridge(self) -> MarketDataBridge:
        """Get market data bridge."""
        return self.container.resolve(MarketDataBridge)

    @property
    def broker_client(self) -> IBrokerClient:
        """Get broker client."""
        return self.container.resolve(IBrokerClient)


# Global application instance
_app: Optional[ApplicationBootstrap] = None


def get_app() -> ApplicationBootstrap:
    """
    Get or create the global application instance.

    Returns:
        ApplicationBootstrap instance
    """
    global _app
    if _app is None:
        _app = ApplicationBootstrap()
        _app.configure()
    return _app


def initialize_app(config: Optional[AppConfig] = None) -> ApplicationBootstrap:
    """
    Initialize the global application instance.

    Args:
        config: Optional application configuration

    Returns:
        ApplicationBootstrap instance
    """
    global _app
    _app = ApplicationBootstrap(config)
    _app.configure()
    return _app
