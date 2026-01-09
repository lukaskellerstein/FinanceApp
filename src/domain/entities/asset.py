"""
Asset entity - Represents a tradeable asset.

Decoupled from database and ibapi dependencies.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum
from datetime import date, datetime


class AssetType(Enum):
    """Type of tradeable asset."""

    NONE = "none"
    STOCK = "stock"
    FUTURE = "future"
    OPTION = "option"
    ETF = "etf"

    @staticmethod
    def from_str(value: str) -> AssetType:
        """
        Create AssetType from string.

        Args:
            value: String value (case-insensitive)

        Returns:
            Corresponding AssetType or NONE if not found
        """
        value_lower = value.lower()
        for asset_type in AssetType:
            if asset_type.value == value_lower:
                return asset_type
        return AssetType.NONE

    def __str__(self) -> str:
        return self.value


@dataclass
class Asset:
    """
    Represents a tradeable asset.

    This is a pure domain entity, decoupled from database (DBObject)
    and external API dependencies.

    Attributes:
        symbol: Primary symbol (e.g., "AAPL", "ES")
        asset_type: Type of asset (STOCK, FUTURE, etc.)
        short_description: Brief description
        contract_details: List of contract details for this asset
        metadata: Additional metadata
    """

    symbol: str
    asset_type: AssetType = AssetType.NONE
    short_description: str = ""
    contract_details: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # For database compatibility
    _id: Optional[str] = None

    def latest_contract_details(self, count: int = 1) -> List[Any]:
        """
        Get the latest contract details.

        For stocks, returns the most recent contracts.
        For futures, filters out expired contracts and returns the nearest.

        Args:
            count: Number of contracts to return

        Returns:
            List of contract details (up to count)
        """
        if not self.contract_details:
            return []

        if self.asset_type in (AssetType.STOCK, AssetType.ETF):
            sorted_details = sorted(
                self.contract_details,
                key=lambda x: getattr(
                    getattr(x, "contract", x),
                    "last_trade_date",
                    "",
                ),
            )
            return sorted_details[:count]

        elif self.asset_type == AssetType.FUTURE:
            # Filter out expired contracts
            today = date.today()
            valid_contracts = [
                cd
                for cd in self.contract_details
                if self._is_contract_valid(cd, today)
            ]
            # Sort by expiration date
            sorted_details = sorted(
                valid_contracts,
                key=lambda x: getattr(
                    getattr(x, "contract", x),
                    "last_trade_date",
                    "",
                ),
            )
            return sorted_details[:count]

        return self.contract_details[:count]

    def _is_contract_valid(self, contract_detail: Any, today: date) -> bool:
        """Check if a contract is still valid (not expired)."""
        try:
            contract = getattr(contract_detail, "contract", contract_detail)
            last_trade_str = getattr(contract, "last_trade_date", "")

            if not last_trade_str:
                return True

            # Handle different date formats
            if len(last_trade_str) == 8:  # YYYYMMDD
                last_date = datetime.strptime(last_trade_str, "%Y%m%d").date()
            else:
                last_date = datetime.strptime(last_trade_str[:10], "%Y-%m-%d").date()

            return last_date >= today
        except (ValueError, AttributeError):
            return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "symbol": self.symbol,
            "type": self.asset_type.value,
            "shortDescription": self.short_description,
            "contractDetails": [
                cd.to_dict() if hasattr(cd, "to_dict") else cd
                for cd in self.contract_details
            ],
            "metadata": self.metadata,
            "_id": self._id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Asset:
        """
        Create from dictionary.

        Args:
            data: Dictionary with asset data

        Returns:
            New Asset instance
        """
        from src.domain.entities.contract_details import ContractDetails

        contract_details = []
        for cd_data in data.get("contractDetails", []):
            if isinstance(cd_data, dict):
                contract_details.append(ContractDetails.from_dict(cd_data))
            else:
                contract_details.append(cd_data)

        return cls(
            symbol=data.get("symbol", ""),
            asset_type=AssetType.from_str(data.get("type", "none")),
            short_description=data.get("shortDescription", ""),
            contract_details=contract_details,
            metadata=data.get("metadata", {}),
            _id=data.get("_id"),
        )

    def __str__(self) -> str:
        return f"Asset({self.symbol}, {self.asset_type.value})"

    def __repr__(self) -> str:
        return (
            f"Asset(symbol={self.symbol!r}, asset_type={self.asset_type}, "
            f"short_description={self.short_description!r})"
        )
