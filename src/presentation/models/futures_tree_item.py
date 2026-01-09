"""
Tree item for futures watchlist hierarchy.

Represents nodes in the futures tree:
- Parent nodes: futures symbols (CL, ES, GC)
- Child nodes: individual contracts (CLZ4, CLM4, ESH5)
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class FuturesTreeItem:
    """
    Represents a node in the futures tree.

    Parent nodes represent futures symbols (CL, ES, GC).
    Child nodes represent individual contracts (CLZ4, CLM4).

    Attributes:
        symbol: Parent symbol (CL, ES, GC)
        local_symbol: Contract symbol (CLZ4, ESH5) - empty for parent rows
        contract_month: Contract month code (202412) - empty for parent rows
        last_trade_date: Expiration date (20241120) - empty for parent rows
        is_parent: True for parent rows, False for contract rows
        parent: Reference to parent item (None for root items)
        children: List of child items (empty for contract rows)

    Tick data fields store real-time market data.
    """

    symbol: str
    local_symbol: str = ""
    contract_month: str = ""
    last_trade_date: str = ""
    is_parent: bool = True
    parent: Optional["FuturesTreeItem"] = None
    children: List["FuturesTreeItem"] = field(default_factory=list)

    # Real-time tick data
    bid: float = 0.0
    bid_size: int = 0
    ask: float = 0.0
    ask_size: int = 0
    last: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0
    change: float = 0.0
    option_historical_vol: float = 0.0
    option_implied_vol: float = 0.0

    def child_count(self) -> int:
        """Return the number of children."""
        return len(self.children)

    def child(self, row: int) -> Optional["FuturesTreeItem"]:
        """
        Get child at the given row index.

        Args:
            row: Row index (0-based)

        Returns:
            Child item or None if index out of range
        """
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def row(self) -> int:
        """
        Get this item's row index within its parent.

        Returns:
            Row index, or 0 if no parent
        """
        if self.parent and self in self.parent.children:
            return self.parent.children.index(self)
        return 0

    def add_child(self, item: "FuturesTreeItem") -> None:
        """
        Add a child item.

        Args:
            item: Child item to add
        """
        item.parent = self
        self.children.append(item)

    def remove_child(self, item: "FuturesTreeItem") -> bool:
        """
        Remove a child item.

        Args:
            item: Child item to remove

        Returns:
            True if removed, False if not found
        """
        if item in self.children:
            self.children.remove(item)
            item.parent = None
            return True
        return False

    def clear_children(self) -> None:
        """Remove all children."""
        for child in self.children:
            child.parent = None
        self.children.clear()

    def update_tick(self, field_name: str, value: Any) -> bool:
        """
        Update a tick field.

        Args:
            field_name: Name of the field to update
            value: New value

        Returns:
            True if the value changed, False otherwise
        """
        if hasattr(self, field_name):
            old_value = getattr(self, field_name)
            if old_value != value:
                setattr(self, field_name, value)
                return True
        return False

    def update_from_tick_data(self, tick_data: dict) -> List[str]:
        """
        Update multiple tick fields from a dictionary.

        Args:
            tick_data: Dictionary with field names and values

        Returns:
            List of field names that were changed
        """
        changed_fields = []
        for field_name, value in tick_data.items():
            if value is not None and self.update_tick(field_name, value):
                changed_fields.append(field_name)

        # Calculate change percentage if we have last and close prices
        if self.last > 0 and self.close > 0:
            new_change = ((self.last - self.close) / self.close) * 100
            if self.update_tick("change", new_change):
                changed_fields.append("change")

        return changed_fields

    @property
    def display_symbol(self) -> str:
        """Get the symbol to display (local_symbol for contracts, symbol for parents)."""
        return self.local_symbol if self.local_symbol else self.symbol

    @property
    def key(self) -> tuple:
        """Get the unique key for this item: (symbol, local_symbol)."""
        return (self.symbol, self.local_symbol)

    def __repr__(self) -> str:
        if self.is_parent:
            return f"FuturesTreeItem(symbol={self.symbol}, children={len(self.children)})"
        return f"FuturesTreeItem(symbol={self.symbol}, local={self.local_symbol})"
