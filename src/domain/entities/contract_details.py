"""
ContractDetails entity - Extended contract information.

Decoupled from ibapi ContractDetails class.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from src.domain.entities.contract import Contract


@dataclass
class ContractDetails:
    """
    Extended contract information from the broker.

    Contains detailed information about a contract including
    trading hours, market rules, and contract specifications.

    This is a pure domain entity, decoupled from ibapi.ContractDetails.
    """

    contract: Contract = field(default_factory=Contract)

    # Contract identification
    market_name: str = ""
    min_tick: float = 0.0
    order_types: str = ""
    valid_exchanges: str = ""

    # Price magnifier for display
    price_magnifier: int = 1

    # Underlying info
    under_con_id: int = 0
    long_name: str = ""
    contract_month: str = ""

    # Industry classification
    industry: str = ""
    category: str = ""
    subcategory: str = ""

    # Time zone and trading hours
    time_zone_id: str = ""
    trading_hours: str = ""
    liquid_hours: str = ""

    # Economic value
    ev_rule: str = ""
    ev_multiplier: float = 0.0

    # Market data
    md_size_multiplier: int = 1

    # Aggregated group
    agg_group: int = 0

    # Underlying symbol
    under_symbol: str = ""
    under_sec_type: str = ""

    # Market rules
    market_rule_ids: str = ""

    # Real expiration date
    real_expiration_date: str = ""

    # Last trade time
    last_trade_time: str = ""

    # Stock type (for stocks)
    stock_type: str = ""

    # Minimum size
    min_size: float = 0.0
    size_increment: float = 0.0
    suggested_size_increment: float = 0.0

    # Bonds specific
    cusip: str = ""
    ratings: str = ""
    desc_append: str = ""
    bond_type: str = ""
    coupon_type: str = ""
    callable: bool = False
    puttable: bool = False
    coupon: float = 0.0
    convertible: bool = False
    maturity: str = ""
    issue_date: str = ""
    next_option_date: str = ""
    next_option_type: str = ""
    next_option_partial: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "contract": self.contract.to_dict(),
            "marketName": self.market_name,
            "minTick": self.min_tick,
            "orderTypes": self.order_types,
            "validExchanges": self.valid_exchanges,
            "priceMagnifier": self.price_magnifier,
            "underConId": self.under_con_id,
            "longName": self.long_name,
            "contractMonth": self.contract_month,
            "industry": self.industry,
            "category": self.category,
            "subcategory": self.subcategory,
            "timeZoneId": self.time_zone_id,
            "tradingHours": self.trading_hours,
            "liquidHours": self.liquid_hours,
            "evRule": self.ev_rule,
            "evMultiplier": self.ev_multiplier,
            "mdSizeMultiplier": self.md_size_multiplier,
            "aggGroup": self.agg_group,
            "underSymbol": self.under_symbol,
            "underSecType": self.under_sec_type,
            "marketRuleIds": self.market_rule_ids,
            "realExpirationDate": self.real_expiration_date,
            "lastTradeTime": self.last_trade_time,
            "stockType": self.stock_type,
            "minSize": self.min_size,
            "sizeIncrement": self.size_increment,
            "suggestedSizeIncrement": self.suggested_size_increment,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ContractDetails:
        """Create from dictionary."""
        contract_data = data.get("contract", {})
        contract = (
            Contract.from_dict(contract_data)
            if isinstance(contract_data, dict)
            else contract_data
        )

        return cls(
            contract=contract,
            market_name=data.get("marketName", ""),
            min_tick=data.get("minTick", 0.0),
            order_types=data.get("orderTypes", ""),
            valid_exchanges=data.get("validExchanges", ""),
            price_magnifier=data.get("priceMagnifier", 1),
            under_con_id=data.get("underConId", 0),
            long_name=data.get("longName", ""),
            contract_month=data.get("contractMonth", ""),
            industry=data.get("industry", ""),
            category=data.get("category", ""),
            subcategory=data.get("subcategory", ""),
            time_zone_id=data.get("timeZoneId", ""),
            trading_hours=data.get("tradingHours", ""),
            liquid_hours=data.get("liquidHours", ""),
            ev_rule=data.get("evRule", ""),
            ev_multiplier=data.get("evMultiplier", 0.0),
            md_size_multiplier=data.get("mdSizeMultiplier", 1),
            agg_group=data.get("aggGroup", 0),
            under_symbol=data.get("underSymbol", ""),
            under_sec_type=data.get("underSecType", ""),
            market_rule_ids=data.get("marketRuleIds", ""),
            real_expiration_date=data.get("realExpirationDate", ""),
            last_trade_time=data.get("lastTradeTime", ""),
            stock_type=data.get("stockType", ""),
            min_size=data.get("minSize", 0.0),
            size_increment=data.get("sizeIncrement", 0.0),
            suggested_size_increment=data.get("suggestedSizeIncrement", 0.0),
        )

    @property
    def symbol(self) -> str:
        """Get the contract symbol."""
        return self.contract.symbol

    @property
    def local_symbol(self) -> str:
        """Get the contract local symbol."""
        return self.contract.local_symbol

    @property
    def sec_type(self) -> str:
        """Get the security type."""
        return self.contract.sec_type

    @property
    def key(self) -> str:
        """Get unique key for this contract details."""
        return self.contract.key

    def __str__(self) -> str:
        return f"ContractDetails({self.contract.symbol}, {self.long_name})"
