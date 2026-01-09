"""
Draggable QTableWidget for watchlist row reordering.

Supports internal drag-and-drop to reorder rows and emits
order_changed signal with the new symbol order.
"""

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QRect
from PyQt6.QtGui import QBrush, QFont, QDrag, QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QStyle,
)

log = logging.getLogger("CellarLogger")


class DraggableWatchlistTable(QTableWidget):
    """
    QTableWidget with internal row drag-and-drop reordering.

    Emits order_changed signal with the new list of symbols after a drop.

    Usage:
        table = DraggableWatchlistTable(symbol_column=1)
        table.order_changed.connect(self._on_order_changed)
    """

    order_changed = pyqtSignal(list)  # Emits [symbol1, symbol2, ...]

    # Custom MIME type to identify our drag data
    MIME_TYPE = "application/x-watchlist-row"

    def __init__(self, symbol_column: int = 1, parent=None):
        """
        Initialize draggable table.

        Args:
            symbol_column: Column index containing symbol text (default: 1)
            parent: Parent widget
        """
        super().__init__(parent)
        self._symbol_column = symbol_column
        self._is_dragging = False
        self._drag_source_row = -1
        self._drop_indicator_row = -1
        self._setup_drag_drop()

    def _setup_drag_drop(self) -> None:
        """Configure drag-drop settings for internal row moves."""
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        # Use DragDrop mode instead of InternalMove to have full control
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Select entire rows for dragging
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    @property
    def symbol_column(self) -> int:
        """Get the column index containing symbols."""
        return self._symbol_column

    @symbol_column.setter
    def symbol_column(self, value: int) -> None:
        """Set the column index containing symbols."""
        self._symbol_column = value

    @property
    def is_dragging(self) -> bool:
        """Check if currently in drag operation."""
        return self._is_dragging

    def startDrag(self, supportedActions: Qt.DropAction) -> None:
        """Start drag operation with custom MIME data and visual preview."""
        self._is_dragging = True
        self._drag_source_row = self.currentRow()

        if self._drag_source_row < 0:
            self._is_dragging = False
            return

        # Create drag with custom MIME data
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData(self.MIME_TYPE, str(self._drag_source_row).encode())
        drag.setMimeData(mime_data)

        # Create a visual preview of the row being dragged
        pixmap = self._create_row_pixmap(self._drag_source_row)
        if pixmap:
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(pixmap.width() // 2, pixmap.height() // 2))

        # Execute drag
        drag.exec(Qt.DropAction.MoveAction)

        self._is_dragging = False
        self._drag_source_row = -1
        self._drop_indicator_row = -1
        self.viewport().update()

    def _create_row_pixmap(self, row: int) -> Optional[QPixmap]:
        """Create a pixmap preview of the row being dragged."""
        if row < 0 or row >= self.rowCount():
            return None

        # Get row height and visible width
        row_height = self.rowHeight(row)
        total_width = min(self.viewport().width(), 400)  # Limit width for preview

        # Create pixmap
        pixmap = QPixmap(total_width, row_height)
        pixmap.fill(QColor(70, 130, 180, 200))  # Semi-transparent steel blue

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(self.font())

        # Draw symbol text in the preview
        symbol_item = self.item(row, self._symbol_column)
        if symbol_item:
            symbol_text = symbol_item.text()
            painter.drawText(
                QRect(10, 0, total_width - 20, row_height),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"Moving: {symbol_text}"
            )

        painter.end()
        return pixmap

    def dragEnterEvent(self, event) -> None:
        """Accept drag if it's from this table."""
        if event.source() == self and event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        """Accept drag move and update drop indicator."""
        if event.source() == self and event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()

            # Calculate which row we're hovering over
            drop_pos = event.position().toPoint()
            index = self.indexAt(drop_pos)
            new_indicator_row = index.row() if index.isValid() else self.rowCount()

            # Update drop indicator if it changed
            if new_indicator_row != self._drop_indicator_row:
                self._drop_indicator_row = new_indicator_row
                self.viewport().update()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        """Clear drop indicator when drag leaves."""
        self._drop_indicator_row = -1
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event) -> None:
        """Paint the table and drop indicator line."""
        super().paintEvent(event)

        # Draw drop indicator line
        if self._is_dragging and self._drop_indicator_row >= 0:
            painter = QPainter(self.viewport())
            painter.setPen(QColor(65, 105, 225))  # Royal blue
            painter.setBrush(QColor(65, 105, 225))

            # Calculate Y position for the indicator line
            if self._drop_indicator_row < self.rowCount():
                y = self.rowViewportPosition(self._drop_indicator_row)
            else:
                # Below last row
                if self.rowCount() > 0:
                    last_row = self.rowCount() - 1
                    y = self.rowViewportPosition(last_row) + self.rowHeight(last_row)
                else:
                    y = 0

            # Draw a thick horizontal line as drop indicator
            line_height = 3
            painter.fillRect(0, y - line_height // 2, self.viewport().width(), line_height, QColor(65, 105, 225))

            # Draw small triangles at the edges for visibility
            triangle_size = 8
            # Left triangle
            painter.drawPolygon([
                QPoint(0, y - triangle_size),
                QPoint(triangle_size, y),
                QPoint(0, y + triangle_size),
            ])
            # Right triangle
            right_x = self.viewport().width()
            painter.drawPolygon([
                QPoint(right_x, y - triangle_size),
                QPoint(right_x - triangle_size, y),
                QPoint(right_x, y + triangle_size),
            ])

            painter.end()

    def dropEvent(self, event) -> None:
        """Handle drop - move the row and emit the new order."""
        self._drop_indicator_row = -1

        if event.source() != self:
            event.ignore()
            return

        if not event.mimeData().hasFormat(self.MIME_TYPE):
            event.ignore()
            return

        # Get source row from MIME data
        try:
            source_row = int(event.mimeData().data(self.MIME_TYPE).data().decode())
        except (ValueError, AttributeError):
            event.ignore()
            return

        # Validate source row
        if source_row < 0 or source_row >= self.rowCount():
            event.ignore()
            return

        # Get the target row from drop position
        drop_pos = event.position().toPoint()
        drop_row = self.indexAt(drop_pos).row()

        # If dropped below all rows, insert at the end
        if drop_row < 0:
            drop_row = self.rowCount()

        # Don't move to same position
        if source_row == drop_row or source_row == drop_row - 1:
            event.ignore()
            return

        # Get symbol before move for logging
        symbol_item = self.item(source_row, self._symbol_column)
        symbol = symbol_item.text() if symbol_item else "unknown"

        log.debug(f"Moving row {source_row} ({symbol}) to position {drop_row}")

        # Block signals during row manipulation to avoid partial updates
        self.blockSignals(True)
        try:
            self._move_row(source_row, drop_row)
        finally:
            self.blockSignals(False)

        # Emit the new symbol order
        symbols = self._get_symbol_order()
        log.debug(f"Row moved: {symbol}, new order: {symbols}")
        self.order_changed.emit(symbols)

        event.acceptProposedAction()
        self.viewport().update()

    def _move_row(self, from_row: int, to_row: int) -> None:
        """
        Move a row from one position to another, preserving all data.

        Note: Cell widgets (buttons) need to be recreated by the parent
        via the order_changed signal handler.
        """
        # Store the source row's data
        row_data = self._extract_row_data(from_row)

        # Remove source row
        self.removeRow(from_row)

        # Adjust target row index if source was above target
        if from_row < to_row:
            to_row -= 1

        # Insert at new position
        self.insertRow(to_row)
        self._restore_row_data(to_row, row_data)

        # Select the moved row
        self.selectRow(to_row)

    def _extract_row_data(self, row: int) -> List[Optional[Dict[str, Any]]]:
        """
        Extract all item data from a row.

        Returns list of dicts with item properties, or None for cells with widgets.
        """
        data = []
        for col in range(self.columnCount()):
            # Cell widgets (buttons) can't be extracted - mark as None
            widget = self.cellWidget(row, col)
            if widget:
                data.append(None)
            else:
                item = self.item(row, col)
                if item:
                    # Get alignment - ensure vertical center is included
                    alignment = item.textAlignment()
                    # If no vertical alignment set, add vertical center
                    if not (alignment & Qt.AlignmentFlag.AlignTop or
                            alignment & Qt.AlignmentFlag.AlignBottom or
                            alignment & Qt.AlignmentFlag.AlignVCenter):
                        alignment = alignment | Qt.AlignmentFlag.AlignVCenter

                    data.append({
                        "text": item.text(),
                        "font": QFont(item.font()),
                        "foreground": QBrush(item.foreground()),
                        "background": QBrush(item.background()),
                        "text_alignment": alignment,
                        "flags": item.flags(),
                        "tool_tip": item.toolTip(),
                    })
                else:
                    data.append(None)
        return data

    def _restore_row_data(self, row: int, data: List[Optional[Dict[str, Any]]]) -> None:
        """Restore row data from extracted list."""
        for col, item_data in enumerate(data):
            if item_data is not None:
                item = QTableWidgetItem(item_data["text"])
                if "font" in item_data:
                    item.setFont(item_data["font"])
                if "foreground" in item_data:
                    item.setForeground(item_data["foreground"])
                if "background" in item_data:
                    item.setBackground(item_data["background"])
                if "text_alignment" in item_data:
                    item.setTextAlignment(item_data["text_alignment"])
                if "flags" in item_data:
                    item.setFlags(item_data["flags"])
                if "tool_tip" in item_data:
                    item.setToolTip(item_data["tool_tip"])
                self.setItem(row, col, item)
            # Cells with widgets (None) will be handled by parent

    def _get_symbol_order(self) -> List[str]:
        """Get current symbol order from all rows."""
        symbols = []
        for row in range(self.rowCount()):
            item = self.item(row, self._symbol_column)
            if item and item.text():
                symbols.append(item.text())
        return symbols
