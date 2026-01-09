"""
Contract entity - Represents a tradeable contract.

Decoupled from ibapi Contract class.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum


class SecType(Enum):
    """Security type enumeration."""

    STOCK = "STK"
    FUTURE = "FUT"
    OPTION = "OPT"
    FOREX = "CASH"
    INDEX = "IND"
    CFD = "CFD"
    BOND = "BOND"
    FUND = "FUND"
    UNKNOWN = ""

    @staticmethod
    def from_str(value: str) -> SecType:
        """Create SecType from string."""
        value_upper = value.upper()
        for sec_type in SecType:
            if sec_type.value == value_upper:
                return sec_type
        return SecType.UNKNOWN


@dataclass
class Contract:
    """
    Base contract class - represents a tradeable instrument.

    This is a pure domain entity, decoupled from ibapi.Contract.
    Contains all fields needed to identify and trade an instrument.

    Attributes:
        con_id: Contract ID from IB
        symbol: Primary symbol
        sec_type: Security type (STK, FUT, OPT, etc.)
        exchange: Exchange name
        currency: Currency code
        local_symbol: Local/exchange-specific symbol
        primary_exchange: Primary exchange
        last_trade_date: Last trade date (YYYYMMDD format)
        multiplier: Contract multiplier
        trading_class: Trading class
    """

    con_id: int = 0
    symbol: str = ""
    sec_type: str = ""
    exchange: str = ""
    currency: str = "USD"
    local_symbol: str = ""
    primary_exchange: str = ""
    last_trade_date: str = ""
    multiplier: str = ""
    trading_class: str = ""
    include_expired: bool = False

    # Option-specific fields
    strike: float = 0.0
    right: str = ""  # "C" for call, "P" for put

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "conId": self.con_id,
            "symbol": self.symbol,
            "secType": self.sec_type,
            "exchange": self.exchange,
            "currency": self.currency,
            "localSymbol": self.local_symbol,
            "primaryExchange": self.primary_exchange,
            "lastTradeDateOrContractMonth": self.last_trade_date,
            "multiplier": self.multiplier,
            "tradingClass": self.trading_class,
            "includeExpired": self.include_expired,
            "strike": self.strike,
            "right": self.right,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Contract:
        """Create from dictionary."""
        return cls(
            con_id=data.get("conId", 0),
            symbol=data.get("symbol", ""),
            sec_type=data.get("secType", ""),
            exchange=data.get("exchange", ""),
            currency=data.get("currency", "USD"),
            local_symbol=data.get("localSymbol", ""),
            primary_exchange=data.get("primaryExchange", ""),
            last_trade_date=data.get("lastTradeDateOrContractMonth", ""),
            multiplier=data.get("multiplier", ""),
            trading_class=data.get("tradingClass", ""),
            include_expired=data.get("includeExpired", False),
            strike=data.get("strike", 0.0),
            right=data.get("right", ""),
        )

    @property
    def key(self) -> str:
        """Get unique key for this contract."""
        return f"{self.symbol}|{self.local_symbol}"

    def __str__(self) -> str:
        return f"Contract({self.symbol}, {self.sec_type}, {self.local_symbol})"


@dataclass
class StockContract(Contract):
    """
    Stock contract with default values for equities.

    Pre-configured for US stocks on SMART routing.
    """

    sec_type: str = "STK"
    exchange: str = "SMART"
    currency: str = "USD"
    primary_exchange: str = "NASDAQ"

    @classmethod
    def create(
        cls,
        symbol: str,
        exchange: str = "SMART",
        primary_exchange: str = "NASDAQ",
        currency: str = "USD",
    ) -> StockContract:
        """
        Create a stock contract.

        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART)
            primary_exchange: Primary exchange (default: NASDAQ)
            currency: Currency (default: USD)

        Returns:
            New StockContract instance
        """
        return cls(
            symbol=symbol,
            local_symbol=symbol,
            exchange=exchange,
            primary_exchange=primary_exchange,
            currency=currency,
        )


@dataclass
class FutureContract(Contract):
    """
    Future contract with default values.

    Pre-configured for futures trading.
    """

    sec_type: str = "FUT"
    currency: str = "USD"
    include_expired: bool = True

    @classmethod
    def create(
        cls,
        symbol: str,
        exchange: str = "",
        local_symbol: str = "",
        last_trade_date: str = "",
        multiplier: str = "",
        currency: str = "USD",
    ) -> FutureContract:
        """
        Create a future contract.

        Args:
            symbol: Future symbol (e.g., "ES")
            exchange: Exchange (e.g., "CME")
            local_symbol: Local symbol (e.g., "ESH5")
            last_trade_date: Expiration date (YYYYMMDD)
            multiplier: Contract multiplier
            currency: Currency (default: USD)

        Returns:
            New FutureContract instance
        """
        return cls(
            symbol=symbol,
            exchange=exchange,
            local_symbol=local_symbol,  # Leave empty for searches
            last_trade_date=last_trade_date,
            multiplier=multiplier,
            currency=currency,
        )


@dataclass
class OptionContract(Contract):
    """
    Option contract with default values.

    Pre-configured for options trading.
    """

    sec_type: str = "OPT"
    currency: str = "USD"

    @classmethod
    def create(
        cls,
        symbol: str,
        strike: float,
        right: str,
        last_trade_date: str,
        exchange: str = "SMART",
        multiplier: str = "100",
        currency: str = "USD",
    ) -> OptionContract:
        """
        Create an option contract.

        Args:
            symbol: Underlying symbol
            strike: Strike price
            right: "C" for call, "P" for put
            last_trade_date: Expiration date (YYYYMMDD)
            exchange: Exchange (default: SMART)
            multiplier: Contract multiplier (default: 100)
            currency: Currency (default: USD)

        Returns:
            New OptionContract instance
        """
        return cls(
            symbol=symbol,
            strike=strike,
            right=right,
            last_trade_date=last_trade_date,
            exchange=exchange,
            multiplier=multiplier,
            currency=currency,
        )

    @property
    def is_call(self) -> bool:
        """Check if this is a call option."""
        return self.right.upper() == "C"

    @property
    def is_put(self) -> bool:
        """Check if this is a put option."""
        return self.right.upper() == "P"
