"""
Watchlist entity - Represents a named collection of symbols.

Supports multiple watchlists per asset type with persistence.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from src.domain.entities.asset import AssetType


@dataclass
class Watchlist:
    """
    Represents a named watchlist containing symbols.

    Attributes:
        id: Unique identifier for the watchlist
        name: Display name of the watchlist
        asset_type: Type of assets in this watchlist (STOCK, FUTURE)
        symbols: List of symbols in this watchlist
        created_at: Creation timestamp
        is_default: Whether this is the default watchlist
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Default"
    asset_type: AssetType = AssetType.NONE
    symbols: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    is_default: bool = False

    def add_symbol(self, symbol: str) -> bool:
        """
        Add a symbol to the watchlist.

        Args:
            symbol: Symbol to add

        Returns:
            True if added, False if already exists
        """
        if symbol not in self.symbols:
            self.symbols.append(symbol)
            return True
        return False

    def remove_symbol(self, symbol: str) -> bool:
        """
        Remove a symbol from the watchlist.

        Args:
            symbol: Symbol to remove

        Returns:
            True if removed, False if not found
        """
        if symbol in self.symbols:
            self.symbols.remove(symbol)
            return True
        return False

    def has_symbol(self, symbol: str) -> bool:
        """Check if symbol is in the watchlist."""
        return symbol in self.symbols

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "asset_type": self.asset_type.value,
            "symbols": self.symbols.copy(),
            "created_at": self.created_at.isoformat(),
            "is_default": self.is_default,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Watchlist:
        """
        Create from dictionary.

        Args:
            data: Dictionary with watchlist data

        Returns:
            New Watchlist instance
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "Default"),
            asset_type=AssetType.from_str(data.get("asset_type", "none")),
            symbols=data.get("symbols", []).copy(),
            created_at=created_at,
            is_default=data.get("is_default", False),
        )

    def __str__(self) -> str:
        return f"Watchlist({self.name}, {len(self.symbols)} symbols)"

    def __repr__(self) -> str:
        return (
            f"Watchlist(id={self.id!r}, name={self.name!r}, "
            f"asset_type={self.asset_type}, symbols={self.symbols})"
        )


@dataclass
class WatchlistCollection:
    """
    Collection of watchlists for a single asset type.

    Manages multiple watchlists and tracks the active one.

    Attributes:
        asset_type: Type of assets for this collection
        watchlists: List of watchlists
        active_watchlist_id: ID of the currently active watchlist
    """

    asset_type: AssetType = AssetType.NONE
    watchlists: List[Watchlist] = field(default_factory=list)
    active_watchlist_id: Optional[str] = None

    def get_watchlist(self, watchlist_id: str) -> Optional[Watchlist]:
        """Get a watchlist by ID."""
        for wl in self.watchlists:
            if wl.id == watchlist_id:
                return wl
        return None

    def get_active_watchlist(self) -> Optional[Watchlist]:
        """Get the currently active watchlist."""
        if self.active_watchlist_id:
            return self.get_watchlist(self.active_watchlist_id)
        if self.watchlists:
            return self.watchlists[0]
        return None

    def add_watchlist(self, watchlist: Watchlist) -> None:
        """Add a watchlist to the collection."""
        watchlist.asset_type = self.asset_type
        self.watchlists.append(watchlist)
        if not self.active_watchlist_id:
            self.active_watchlist_id = watchlist.id

    def remove_watchlist(self, watchlist_id: str) -> bool:
        """
        Remove a watchlist by ID.

        Args:
            watchlist_id: ID of watchlist to remove

        Returns:
            True if removed, False if not found
        """
        for i, wl in enumerate(self.watchlists):
            if wl.id == watchlist_id:
                self.watchlists.pop(i)
                # Update active if we removed it
                if self.active_watchlist_id == watchlist_id:
                    self.active_watchlist_id = (
                        self.watchlists[0].id if self.watchlists else None
                    )
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "asset_type": self.asset_type.value,
            "watchlists": [wl.to_dict() for wl in self.watchlists],
            "active_watchlist_id": self.active_watchlist_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WatchlistCollection:
        """Create from dictionary."""
        asset_type = AssetType.from_str(data.get("asset_type", "none"))
        watchlists = [
            Watchlist.from_dict(wl_data)
            for wl_data in data.get("watchlists", [])
        ]
        return cls(
            asset_type=asset_type,
            watchlists=watchlists,
            active_watchlist_id=data.get("active_watchlist_id"),
        )
