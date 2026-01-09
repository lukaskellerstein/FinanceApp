"""
Custom exceptions for the FinanceApp.

Provides a hierarchy of exceptions for different error scenarios:
- Broker errors (connection, request failures)
- Data errors (not found, not available)
- Validation errors
- Configuration errors
"""


class FinanceAppException(Exception):
    """Base exception for all application exceptions."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(self.message)


class BrokerConnectionError(FinanceAppException):
    """Raised when broker connection fails."""

    def __init__(self, message: str = "Failed to connect to broker"):
        super().__init__(message)


class BrokerRequestError(FinanceAppException):
    """Raised when a broker request fails."""

    def __init__(self, message: str, error_code: int = 0):
        super().__init__(message)
        self.error_code = error_code


class AssetNotFoundError(FinanceAppException):
    """Raised when an asset is not found."""

    def __init__(self, asset_type: str, symbol: str):
        self.asset_type = asset_type
        self.symbol = symbol
        super().__init__(f"Asset not found: {asset_type}/{symbol}")


class DataNotAvailableError(FinanceAppException):
    """Raised when requested data is not available."""

    def __init__(
        self,
        symbol: str,
        data_type: str = "data",
        reason: str = "not available",
    ):
        self.symbol = symbol
        self.data_type = data_type
        self.reason = reason
        super().__init__(f"{data_type} for {symbol} is {reason}")


class ValidationError(FinanceAppException):
    """Raised when validation fails."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error for '{field}': {message}")


class ConfigurationError(FinanceAppException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, config_key: str, message: str = "is missing or invalid"):
        self.config_key = config_key
        super().__init__(f"Configuration '{config_key}' {message}")


class ServiceNotRegisteredError(FinanceAppException):
    """Raised when a service is not registered in the DI container."""

    def __init__(self, service_type: type):
        self.service_type = service_type
        super().__init__(f"Service {service_type.__name__} is not registered")
