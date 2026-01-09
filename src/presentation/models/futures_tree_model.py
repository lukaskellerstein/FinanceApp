"""
Qt Tree Model for futures watchlist.

Displays futures as parent rows with contracts as expandable children.
Example:
    CL (Crude Oil)
    ├── CLZ4 (Dec 2024)
    ├── CLF5 (Jan 2025)
    └── CLG5 (Feb 2025)
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    Qt,
)
from PyQt6.QtGui import QColor, QFont

from src.domain.entities.asset import Asset
from src.presentation.models.futures_tree_item import FuturesTreeItem

log = logging.getLogger("CellarLogger")


class FuturesTreeModel(QAbstractItemModel):
    """
    Tree model for futures watchlist.

    Displays futures as parent rows with contracts as children.

    Columns:
        0: Symbol/LocalSymbol
        1: Contract Month
        2: Expiry Date
        3: Bid Size
        4: Bid
        5: Last
        6: Ask
        7: Ask Size
        8: Change %
        9: Open
        10: High
        11: Low
        12: Close
        13: Volume

    Usage:
        model = FuturesTreeModel()
        model.load_assets({"CL": asset_cl, "ES": asset_es})
        tree_view.setModel(model)

        # Real-time updates
        model.update_tick("CL", "CLZ4", {"last": 75.50, "bid": 75.49})
    """

    COLUMNS = [
        "",          # View button
        "Symbol",
        "Month",
        "Expiry",
        "Bid Size",
        "Bid",
        "Last",
        "Ask",
        "Ask Size",
        "Change %",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
        "",          # Delete button
    ]

    # Column indices
    COL_VIEW = 0
    COL_SYMBOL = 1
    COL_MONTH = 2
    COL_EXPIRY = 3
    COL_BID_SIZE = 4
    COL_BID = 5
    COL_LAST = 6
    COL_ASK = 7
    COL_ASK_SIZE = 8
    COL_CHANGE = 9
    COL_OPEN = 10
    COL_HIGH = 11
    COL_LOW = 12
    COL_CLOSE = 13
    COL_VOLUME = 14
    COL_DELETE = 15

    # Field to column mapping for tick updates
    FIELD_TO_COLUMN = {
        "bid": 5,
        "bid_size": 4,
        "ask": 7,
        "ask_size": 8,
        "last": 6,
        "open": 10,
        "high": 11,
        "low": 12,
        "close": 13,
        "volume": 14,
        "change": 9,
    }

    # Light blue background for Last column
    LAST_COLUMN_BACKGROUND = QColor("#e3f2fd")

    def __init__(self, parent=None):
        """Initialize the model."""
        super().__init__(parent)
        self._root_items: List[FuturesTreeItem] = []
        # Quick lookup: (symbol, local_symbol) -> FuturesTreeItem
        self._item_map: Dict[Tuple[str, str], FuturesTreeItem] = {}
        # Track front-month contract for each symbol: symbol -> local_symbol
        self._front_month: Dict[str, str] = {}

    # ---------------------------------------------------------
    # Public API for ViewModel integration
    # ---------------------------------------------------------

    def load_assets(self, assets: Dict[str, Asset]) -> None:
        """
        Load assets into the tree model.

        Replaces all existing data.

        Args:
            assets: Dict mapping symbol to Asset
        """
        self.beginResetModel()
        self._root_items.clear()
        self._item_map.clear()

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)

        for symbol, asset in assets.items():
            log.debug(f"load_assets: {symbol} has {len(asset.contract_details)} contracts")
            # Create parent item for the symbol
            parent_item = FuturesTreeItem(
                symbol=symbol,
                is_parent=True,
            )
            self._root_items.append(parent_item)
            self._item_map[(symbol, "")] = parent_item

            # Track contracts with valid expiry dates to find front-month
            # (local_symbol, expiry_date, contract_month)
            active_contracts: List[Tuple[str, str, str]] = []

            # Sort contract_details by expiry date (closest first)
            sorted_contracts = sorted(
                asset.contract_details,
                key=lambda cd: cd.contract.last_trade_date or "99999999"
            )

            # Add contracts as children (sorted by expiry, closest first)
            for cd in sorted_contracts:
                contract = cd.contract
                log.debug(f"  Adding child: {contract.local_symbol}")
                child_item = FuturesTreeItem(
                    symbol=symbol,
                    local_symbol=contract.local_symbol,
                    contract_month=cd.contract_month or "",
                    last_trade_date=contract.last_trade_date or "",
                    is_parent=False,
                )
                parent_item.add_child(child_item)
                self._item_map[(symbol, contract.local_symbol)] = child_item

                # Track active contracts for front-month determination
                if contract.last_trade_date:
                    try:
                        expiry = datetime.strptime(
                            contract.last_trade_date, "%Y%m%d"
                        ).replace(tzinfo=timezone.utc)
                        if expiry >= now:
                            active_contracts.append((
                                contract.local_symbol,
                                contract.last_trade_date,
                                cd.contract_month or ""
                            ))
                    except ValueError:
                        pass

            # Determine front-month (nearest active contract)
            if active_contracts:
                active_contracts.sort(key=lambda x: x[1])  # Sort by expiry date
                front_local, front_expiry, front_month = active_contracts[0]
                self._front_month[symbol] = front_local
                # Copy front-month's month and expiry to parent for display when collapsed
                parent_item.contract_month = front_month
                parent_item.last_trade_date = front_expiry
                log.debug(f"  Front-month for {symbol}: {front_local}")

        self.endResetModel()
        log.debug(f"Loaded {len(self._root_items)} futures into tree model, item_map keys: {list(self._item_map.keys())}")

    def add_symbol(self, symbol: str, asset: Asset) -> None:
        """
        Add a new symbol (parent) with its contracts.

        Args:
            symbol: Symbol to add
            asset: Asset with contract details
        """
        from datetime import datetime, timezone

        # Check if already exists
        if (symbol, "") in self._item_map:
            log.warning(f"Symbol {symbol} already in tree model")
            return

        now = datetime.now(timezone.utc)
        row = len(self._root_items)
        self.beginInsertRows(QModelIndex(), row, row)

        parent_item = FuturesTreeItem(symbol=symbol, is_parent=True)
        self._root_items.append(parent_item)
        self._item_map[(symbol, "")] = parent_item

        # Track active contracts for front-month determination
        # (local_symbol, expiry_date, contract_month)
        active_contracts: List[Tuple[str, str, str]] = []

        # Sort contract_details by expiry date (closest first)
        sorted_contracts = sorted(
            asset.contract_details,
            key=lambda cd: cd.contract.last_trade_date or "99999999"
        )

        for cd in sorted_contracts:
            contract = cd.contract
            child_item = FuturesTreeItem(
                symbol=symbol,
                local_symbol=contract.local_symbol,
                contract_month=cd.contract_month or "",
                last_trade_date=contract.last_trade_date or "",
                is_parent=False,
            )
            parent_item.add_child(child_item)
            self._item_map[(symbol, contract.local_symbol)] = child_item

            # Track active contracts
            if contract.last_trade_date:
                try:
                    expiry = datetime.strptime(
                        contract.last_trade_date, "%Y%m%d"
                    ).replace(tzinfo=timezone.utc)
                    if expiry >= now:
                        active_contracts.append((
                            contract.local_symbol,
                            contract.last_trade_date,
                            cd.contract_month or ""
                        ))
                except ValueError:
                    pass

        # Determine front-month
        if active_contracts:
            active_contracts.sort(key=lambda x: x[1])
            front_local, front_expiry, front_month = active_contracts[0]
            self._front_month[symbol] = front_local
            # Copy front-month's month and expiry to parent for display when collapsed
            parent_item.contract_month = front_month
            parent_item.last_trade_date = front_expiry
            log.debug(f"Front-month for {symbol}: {front_local}")

        self.endInsertRows()
        log.debug(f"Added {symbol} with {parent_item.child_count()} contracts")

    def remove_symbol(self, symbol: str) -> None:
        """
        Remove a symbol and all its contracts.

        Args:
            symbol: Symbol to remove
        """
        for i, item in enumerate(self._root_items):
            if item.symbol == symbol:
                self.beginRemoveRows(QModelIndex(), i, i)

                # Remove from map
                self._item_map.pop((symbol, ""), None)
                for child in item.children:
                    self._item_map.pop((symbol, child.local_symbol), None)

                # Remove front-month tracking
                self._front_month.pop(symbol, None)

                self._root_items.pop(i)
                self.endRemoveRows()
                log.debug(f"Removed {symbol} from tree model")
                break

    def update_tick(
        self, symbol: str, local_symbol: str, tick_data: dict
    ) -> None:
        """
        Update tick data for a specific contract.

        Also updates the parent row if this is the front-month contract.

        Args:
            symbol: Parent symbol (CL, ES)
            local_symbol: Contract symbol (CLZ4, ESH5)
            tick_data: Dict with tick fields (bid, ask, last, etc.)
        """
        item = self._item_map.get((symbol, local_symbol))
        if not item:
            log.debug(f"update_tick: No item found for ({symbol}, {local_symbol}), available keys: {list(self._item_map.keys())[:10]}")
            return

        # Update the child item and get changed fields
        changed_fields = item.update_from_tick_data(tick_data)

        if changed_fields:
            # Find the columns that changed
            changed_columns = []
            for field_name in changed_fields:
                if field_name in self.FIELD_TO_COLUMN:
                    changed_columns.append(self.FIELD_TO_COLUMN[field_name])

            if changed_columns:
                # Emit dataChanged for the child item
                index = self._index_for_item(item)
                if index.isValid():
                    min_col = min(changed_columns)
                    max_col = max(changed_columns)
                    top_left = self.index(index.row(), min_col, index.parent())
                    bottom_right = self.index(index.row(), max_col, index.parent())
                    self.dataChanged.emit(top_left, bottom_right)

        # If this is the front-month contract, also update the parent row
        front_month = self._front_month.get(symbol)
        if front_month and front_month == local_symbol:
            parent_item = self._item_map.get((symbol, ""))
            if parent_item:
                parent_changed = parent_item.update_from_tick_data(tick_data)
                if parent_changed:
                    # Find columns that changed for parent
                    parent_columns = []
                    for field_name in parent_changed:
                        if field_name in self.FIELD_TO_COLUMN:
                            parent_columns.append(self.FIELD_TO_COLUMN[field_name])

                    if parent_columns:
                        parent_index = self._index_for_item(parent_item)
                        if parent_index.isValid():
                            min_col = min(parent_columns)
                            max_col = max(parent_columns)
                            top_left = self.index(parent_index.row(), min_col, QModelIndex())
                            bottom_right = self.index(parent_index.row(), max_col, QModelIndex())
                            self.dataChanged.emit(top_left, bottom_right)

    def clear(self) -> None:
        """Clear all data from the model."""
        self.beginResetModel()
        self._root_items.clear()
        self._item_map.clear()
        self._front_month.clear()
        self.endResetModel()

    def get_item_at_index(self, index: QModelIndex) -> Optional[FuturesTreeItem]:
        """
        Get the FuturesTreeItem at the given index.

        Args:
            index: QModelIndex to query

        Returns:
            FuturesTreeItem or None
        """
        if not index.isValid():
            return None
        return index.internalPointer()

    def get_symbol_at_index(self, index: QModelIndex) -> Optional[str]:
        """
        Get the symbol at the given index.

        Args:
            index: QModelIndex to query

        Returns:
            Symbol string or None
        """
        item = self.get_item_at_index(index)
        return item.symbol if item else None

    def set_item_expanded(self, index: QModelIndex, expanded: bool) -> None:
        """
        Set the expanded state for a parent item.

        When expanded, parent rows hide their data (children show individual data).
        When collapsed, parent rows show front-month data.

        Args:
            index: Index of the item
            expanded: True if expanded, False if collapsed
        """
        item = self.get_item_at_index(index)
        if item and item.is_parent:
            item.is_expanded = expanded
            # Emit dataChanged for all data columns to refresh display
            top_left = self.index(index.row(), self.COL_BID_SIZE, QModelIndex())
            bottom_right = self.index(index.row(), self.COL_VOLUME, QModelIndex())
            self.dataChanged.emit(top_left, bottom_right)

    # ---------------------------------------------------------
    # Internal helper methods
    # ---------------------------------------------------------

    def _index_for_item(self, item: FuturesTreeItem) -> QModelIndex:
        """Get QModelIndex for an item."""
        if item.is_parent:
            try:
                row = self._root_items.index(item)
                return self.createIndex(row, 0, item)
            except ValueError:
                return QModelIndex()
        else:
            row = item.row()
            return self.createIndex(row, 0, item)

    # ---------------------------------------------------------
    # QAbstractItemModel required methods
    # ---------------------------------------------------------

    def index(
        self, row: int, column: int, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        """
        Create index for item at (row, column) under parent.

        Args:
            row: Row index
            column: Column index
            parent: Parent index

        Returns:
            QModelIndex for the item
        """
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            # Root level item
            if 0 <= row < len(self._root_items):
                return self.createIndex(row, column, self._root_items[row])
        else:
            # Child item
            parent_item = parent.internalPointer()
            if parent_item:
                child = parent_item.child(row)
                if child:
                    return self.createIndex(row, column, child)

        return QModelIndex()

    def parent(self, index: QModelIndex) -> QModelIndex:
        """
        Get parent index of the given index.

        Args:
            index: Child index

        Returns:
            Parent index or invalid index for root items
        """
        if not index.isValid():
            return QModelIndex()

        item = index.internalPointer()
        if not item or item.is_parent:
            return QModelIndex()  # Root items have no parent

        parent_item = item.parent
        if parent_item:
            try:
                row = self._root_items.index(parent_item)
                return self.createIndex(row, 0, parent_item)
            except ValueError:
                return QModelIndex()

        return QModelIndex()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Get number of rows under parent.

        Args:
            parent: Parent index

        Returns:
            Number of child rows
        """
        if not parent.isValid():
            return len(self._root_items)

        item = parent.internalPointer()
        if item:
            return item.child_count()
        return 0

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """
        Get number of columns.

        Args:
            parent: Parent index (ignored)

        Returns:
            Number of columns
        """
        return len(self.COLUMNS)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        """
        Get data for the given index and role.

        Args:
            index: Item index
            role: Data role

        Returns:
            Data for display or None
        """
        if not index.isValid():
            return None

        item = index.internalPointer()
        if not item:
            return None

        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._get_display_data(item, col)

        elif role == Qt.ItemDataRole.BackgroundRole:
            # Light blue background for Last column
            if col == self.COL_LAST:
                return self.LAST_COLUMN_BACKGROUND
            # Color the change column based on value
            if col == self.COL_CHANGE and item.change != 0:
                return self._get_change_color(item.change)

        elif role == Qt.ItemDataRole.ForegroundRole:
            # Black text for Last column (for prominence on light blue background)
            if col == self.COL_LAST:
                return QColor("black")
            # Red text for Delete column (matching stocks watchlist style)
            if col == self.COL_DELETE and item.is_parent:
                return QColor("red")
            # Text color based on background luminance for Change column
            if col == self.COL_CHANGE and item.change != 0:
                bg_color = self._get_change_color(item.change)
                if bg_color:
                    if self._is_dark_color(bg_color):
                        return QColor("white")
                    else:
                        return QColor("black")

        elif role == Qt.ItemDataRole.FontRole:
            # Bold font for Last column
            if col == self.COL_LAST:
                font = QFont()
                font.setBold(True)
                return font
            # Bold font for Delete column (matching stocks watchlist style)
            if col == self.COL_DELETE and item.is_parent:
                font = QFont()
                font.setBold(True)
                return font

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            # Center-align View and Delete columns
            if col in (self.COL_VIEW, self.COL_DELETE):
                return Qt.AlignmentFlag.AlignCenter
            # Right-align numeric columns
            if col >= self.COL_BID_SIZE and col != self.COL_DELETE:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return None

    def _get_display_data(self, item: FuturesTreeItem, col: int) -> str:
        """Get display string for a cell."""
        if col == self.COL_VIEW:
            # Only show chart icon for parent rows
            return "📈" if item.is_parent else ""
        elif col == self.COL_SYMBOL:
            return item.display_symbol
        elif col == self.COL_MONTH:
            # Hide month for expanded parent rows
            if item.is_parent and item.is_expanded:
                return ""
            return item.contract_month
        elif col == self.COL_EXPIRY:
            # Hide expiry for expanded parent rows
            if item.is_parent and item.is_expanded:
                return ""
            return item.last_trade_date
        elif col == self.COL_BID_SIZE:
            # Hide data for expanded parent rows (children show individual data)
            if item.is_parent and item.is_expanded:
                return ""
            return self._format_size(item.bid_size)
        elif col == self.COL_BID:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.bid:.2f}" if item.bid else "-"
        elif col == self.COL_LAST:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.last:.2f}" if item.last else "-"
        elif col == self.COL_ASK:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.ask:.2f}" if item.ask else "-"
        elif col == self.COL_ASK_SIZE:
            if item.is_parent and item.is_expanded:
                return ""
            return self._format_size(item.ask_size)
        elif col == self.COL_CHANGE:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.change:+.2f}%" if item.change else "-"
        elif col == self.COL_OPEN:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.open:.2f}" if item.open else "-"
        elif col == self.COL_HIGH:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.high:.2f}" if item.high else "-"
        elif col == self.COL_LOW:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.low:.2f}" if item.low else "-"
        elif col == self.COL_CLOSE:
            if item.is_parent and item.is_expanded:
                return ""
            return f"{item.close:.2f}" if item.close else "-"
        elif col == self.COL_VOLUME:
            if item.is_parent and item.is_expanded:
                return ""
            return self._format_volume(item.volume)
        elif col == self.COL_DELETE:
            # Only show delete button for parent rows
            return "X" if item.is_parent else ""
        return ""

    def _format_volume(self, volume: int) -> str:
        """Format volume with K/M suffix for readability."""
        if not volume:
            return "-"
        if volume >= 1_000_000:
            return f"{volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume / 1_000:.1f}K"
        return str(volume)

    def _format_size(self, size: int) -> str:
        """Format size values."""
        if not size:
            return "-"
        if size >= 1_000_000:
            return f"{size / 1_000_000:.1f}M"
        elif size >= 1_000:
            return f"{size / 1_000:.1f}K"
        return str(size)

    def _get_change_color(self, change: float) -> Optional[QColor]:
        """Get background color based on percentage change."""
        if change <= -25:
            return QColor("#b71c1c")
        elif change <= -10:
            return QColor("#d32f2f")
        elif change <= -6:
            return QColor("#f44336")
        elif change <= -3:
            return QColor("#e57373")
        elif change < 0:
            return QColor("#ffcdd2")
        elif change == 0:
            return None
        elif change < 3:
            return QColor("#c8e6c9")
        elif change < 6:
            return QColor("#81c784")
        elif change < 10:
            return QColor("#4caf50")
        elif change < 25:
            return QColor("#388e3c")
        else:
            return QColor("#1b5e20")

    def _is_dark_color(self, color: QColor) -> bool:
        """Check if a color is dark based on luminance."""
        r, g, b = color.red(), color.green(), color.blue()
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """
        Get header data.

        Args:
            section: Column/row index
            orientation: Horizontal or vertical
            role: Data role

        Returns:
            Header text or None
        """
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        Get item flags.

        Args:
            index: Item index

        Returns:
            Item flags
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
