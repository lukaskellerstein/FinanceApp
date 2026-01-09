"""
Application configuration management.

Provides centralized access to configuration values with:
- Environment-based configuration (DEV/PROD)
- Typed configuration objects
- Default values for missing config
"""

from __future__ import annotations
import configparser
import os
from typing import Optional
from enum import Enum
from dataclasses import dataclass
import logging

log = logging.getLogger("CellarLogger")


class Environment(Enum):
    """Application environment."""

    DEV = "dev"
    PROD = "prod"


@dataclass
class BrokerConfig:
    """Interactive Brokers connection configuration."""

    ip: str
    port: int
    client_id: int


@dataclass
class DatabaseConfig:
    """Database paths configuration."""

    assets_path: str
    watchlists_path: str
    historical_data_path: str


class AppConfig:
    """
    Centralized configuration management.

    Reads from config.ini and provides typed configuration objects.
    Supports environment-based configuration (DEV/PROD).

    Example:
        config = AppConfig()
        broker = config.broker_config
        print(f"Connecting to {broker.ip}:{broker.port}")
    """

    _instance: Optional[AppConfig] = None

    def __new__(cls, config_path: str = "config.ini") -> AppConfig:
        """Singleton pattern - only one config instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str = "config.ini"):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.ini file
        """
        if self._initialized:
            return

        self._config = configparser.ConfigParser()
        self._config_path = config_path
        self._environment: Optional[Environment] = None

        # Try to load config file
        if os.path.exists(config_path):
            self._config.read(config_path)
            log.info(f"Configuration loaded from {config_path}")
        else:
            log.warning(f"Config file not found at {config_path}, using defaults")

        self._initialized = True

    @property
    def environment(self) -> Environment:
        """Get current environment (DEV/PROD)."""
        if self._environment is None:
            env_str = self._get_value("APP_SETTINGS", "environment", "dev")
            try:
                self._environment = Environment(env_str.lower())
            except ValueError:
                log.warning(f"Unknown environment: {env_str}, defaulting to DEV")
                self._environment = Environment.DEV
        return self._environment

    @property
    def broker_config(self) -> BrokerConfig:
        """Get broker connection configuration."""
        ip = self._get_value("IB", "tws_ip", "127.0.0.1")

        if self.environment == Environment.DEV:
            port = int(self._get_value("IB", "tws_sim_port", "7497"))
        else:
            port = int(self._get_value("IB", "tws_real_port", "7496"))

        client_id = int(self._get_value("IB", "client_id", "0"))

        return BrokerConfig(ip=ip, port=port, client_id=client_id)

    @property
    def database_config(self) -> DatabaseConfig:
        """Get database paths configuration."""
        base_path = self._get_value("DATABASE", "base_path", "src/db")
        return DatabaseConfig(
            assets_path=os.path.join(base_path, "assets"),
            watchlists_path=os.path.join(base_path, "watchlists"),
            historical_data_path=os.path.join(base_path, "pystore"),
        )

    @property
    def log_level(self) -> str:
        """Get log level."""
        return self._get_value("LOGGING", "level", "INFO")

    def _get_value(self, section: str, key: str, default: str = "") -> str:
        """
        Get a configuration value.

        Args:
            section: Config section name
            key: Key within section
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        try:
            return self._config[section][key]
        except KeyError:
            return default

    def reload(self) -> None:
        """Reload configuration from file."""
        if os.path.exists(self._config_path):
            self._config.read(self._config_path)
            self._environment = None  # Reset cached environment
            log.info("Configuration reloaded")
