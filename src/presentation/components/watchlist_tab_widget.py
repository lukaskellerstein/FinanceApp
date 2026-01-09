"""
Watchlist Tab Widget component.

Custom QTabWidget for managing multiple watchlists with:
- Closable tabs (X button)
- Add new watchlist tab (+)
- Right-click context menu (rename, delete)
- Tab switching signals
"""

from typing import Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QTabWidget,
    QWidget,
    QMessageBox,
    QMenu,
    QInputDialog,
)


class WatchlistTabWidget(QTabWidget):
    """
    Custom tab widget for managing multiple watchlists.

    Signals:
        watchlist_create_requested: Emitted when user clicks + tab
        watchlist_delete_requested(watchlist_id): Emitted when user clicks X or selects delete
        watchlist_rename_requested(watchlist_id, new_name): Emitted when user renames a tab
        watchlist_changed(watchlist_id): Emitted when active tab changes

    Usage:
        tab_widget = WatchlistTabWidget()
        tab_widget.watchlist_create_requested.connect(self._on_create)
        tab_widget.watchlist_delete_requested.connect(self._on_delete)
        tab_widget.watchlist_rename_requested.connect(self._on_rename)
        tab_widget.watchlist_changed.connect(self._on_tab_changed)

        # Add watchlist tabs
        tab_widget.add_watchlist_tab("id1", "Default", content_widget1)
        tab_widget.add_watchlist_tab("id2", "Tech", content_widget2)
    """

    # Signals
    watchlist_create_requested = pyqtSignal()
    watchlist_delete_requested = pyqtSignal(str)  # watchlist_id
    watchlist_rename_requested = pyqtSignal(str, str)  # watchlist_id, new_name
    watchlist_changed = pyqtSignal(str)  # watchlist_id

    # Special marker for the "+" tab
    ADD_TAB_ID = "__add_new_watchlist__"

    def __init__(self, parent=None):
        """Initialize the tab widget."""
        super().__init__(parent)
        self._watchlist_ids: Dict[int, str] = {}  # tab_index -> watchlist_id
        self._context_menu_tab_index: int = -1  # Track which tab was right-clicked
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the tab widget UI."""
        # Disable close buttons - use context menu for delete instead
        self.setTabsClosable(False)

        # Tab changed signal
        self.currentChanged.connect(self._on_current_changed)

        # Enable context menu on tab bar
        self.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabBar().customContextMenuRequested.connect(self._on_tab_context_menu)

        # Add the "+" tab for creating new watchlists
        self._add_plus_tab()

        # Style the tab bar
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                border-top: none;
                background: #2b2b2b;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                background: #3d3d3d;
                color: #a0a0a0;
                border: 1px solid #4d4d4d;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:hover {
                background: #4a4a4a;
                color: #d0d0d0;
            }
            QTabBar::tab:selected {
                background: #2b2b2b;
                color: #ffffff;
                border: 1px solid #007bff;
                border-bottom: 2px solid #2b2b2b;
                font-weight: bold;
            }
        """)

    def _add_plus_tab(self) -> None:
        """Add the '+' tab at the end for creating new watchlists."""
        # Create an empty widget for the + tab
        plus_widget = QWidget()
        plus_widget.setObjectName("plus_tab_widget")
        index = super().addTab(plus_widget, "+")
        self._watchlist_ids[index] = self.ADD_TAB_ID

    def _on_tab_context_menu(self, pos: QPoint) -> None:
        """Handle right-click context menu on tabs."""
        # Get the tab index at the click position
        tab_index = self.tabBar().tabAt(pos)
        if tab_index < 0:
            return

        # Don't show context menu for the + tab
        watchlist_id = self._watchlist_ids.get(tab_index)
        if watchlist_id == self.ADD_TAB_ID:
            return

        self._context_menu_tab_index = tab_index

        # Create context menu
        menu = QMenu(self)

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(self._on_rename_action)
        menu.addAction(rename_action)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._on_delete_action)
        menu.addAction(delete_action)

        # Show menu at cursor position
        menu.exec(self.tabBar().mapToGlobal(pos))

    def _on_rename_action(self) -> None:
        """Handle rename action from context menu."""
        if self._context_menu_tab_index < 0:
            return

        watchlist_id = self._watchlist_ids.get(self._context_menu_tab_index)
        if not watchlist_id or watchlist_id == self.ADD_TAB_ID:
            return

        current_name = self.tabText(self._context_menu_tab_index)

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Watchlist",
            "Enter new name:",
            text=current_name,
        )

        if ok and new_name and new_name != current_name:
            self.setTabText(self._context_menu_tab_index, new_name)
            self.watchlist_rename_requested.emit(watchlist_id, new_name)

        self._context_menu_tab_index = -1

    def _on_delete_action(self) -> None:
        """Handle delete action from context menu."""
        if self._context_menu_tab_index < 0:
            return

        watchlist_id = self._watchlist_ids.get(self._context_menu_tab_index)
        if not watchlist_id or watchlist_id == self.ADD_TAB_ID:
            return

        # Count real watchlists (excluding + tab)
        real_watchlist_count = sum(
            1 for wl_id in self._watchlist_ids.values()
            if wl_id != self.ADD_TAB_ID
        )

        if real_watchlist_count > 1:
            self.watchlist_delete_requested.emit(watchlist_id)
        else:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                "You must have at least one watchlist.",
            )

        self._context_menu_tab_index = -1

    def _on_current_changed(self, index: int) -> None:
        """Handle tab change."""
        watchlist_id = self._watchlist_ids.get(index)

        # If + tab is clicked, switch back first, then emit create signal
        if watchlist_id == self.ADD_TAB_ID:
            # Switch to the previous tab BEFORE showing dialog
            # (dialog is modal, so code after emit() runs after dialog closes)
            if index > 0:
                self.setCurrentIndex(index - 1)
            self.watchlist_create_requested.emit()
            return

        if watchlist_id:
            self.watchlist_changed.emit(watchlist_id)

    def add_watchlist_tab(
        self,
        watchlist_id: str,
        name: str,
        content_widget: QWidget,
    ) -> int:
        """
        Add a new watchlist tab.

        Args:
            watchlist_id: Unique watchlist identifier
            name: Tab display name
            content_widget: Widget to display in the tab

        Returns:
            Tab index
        """
        # Find the + tab index to insert before it
        plus_index = None
        for idx, wl_id in self._watchlist_ids.items():
            if wl_id == self.ADD_TAB_ID:
                plus_index = idx
                break

        if plus_index is not None:
            # Insert before the + tab
            index = self.insertTab(plus_index, content_widget, name)

            # Manually update mapping: shift all indices >= insert point
            new_mapping = {}
            for idx, wl_id in self._watchlist_ids.items():
                if idx >= plus_index:
                    new_mapping[idx + 1] = wl_id  # Shift up by 1
                else:
                    new_mapping[idx] = wl_id
            new_mapping[index] = watchlist_id  # Add the new tab
            self._watchlist_ids = new_mapping
        else:
            # No + tab found, just add at the end
            index = self.addTab(content_widget, name)
            self._watchlist_ids[index] = watchlist_id

        return index

    def remove_watchlist_tab(self, watchlist_id: str) -> bool:
        """
        Remove a watchlist tab by ID.

        Args:
            watchlist_id: Watchlist identifier

        Returns:
            True if removed, False if not found
        """
        for index, wl_id in list(self._watchlist_ids.items()):
            if wl_id == watchlist_id:
                self.removeTab(index)
                self._rebuild_id_mapping()
                return True
        return False

    def set_active_watchlist(self, watchlist_id: str) -> bool:
        """
        Set the active tab by watchlist ID.

        Args:
            watchlist_id: Watchlist identifier

        Returns:
            True if found and set, False otherwise
        """
        for index, wl_id in self._watchlist_ids.items():
            if wl_id == watchlist_id:
                self.setCurrentIndex(index)
                return True
        return False

    def get_active_watchlist_id(self) -> Optional[str]:
        """Get the ID of the currently active watchlist (None if + tab is active)."""
        wl_id = self._watchlist_ids.get(self.currentIndex())
        if wl_id == self.ADD_TAB_ID:
            return None
        return wl_id

    def get_watchlist_ids(self) -> List[str]:
        """Get list of all watchlist IDs in tab order (excluding + tab)."""
        return [
            self._watchlist_ids[i]
            for i in range(self.count())
            if i in self._watchlist_ids and self._watchlist_ids[i] != self.ADD_TAB_ID
        ]

    def rename_tab(self, watchlist_id: str, new_name: str) -> bool:
        """
        Rename a tab by watchlist ID.

        Args:
            watchlist_id: Watchlist identifier
            new_name: New tab name

        Returns:
            True if renamed, False if not found
        """
        for index, wl_id in self._watchlist_ids.items():
            if wl_id == watchlist_id:
                self.setTabText(index, new_name)
                return True
        return False

    def clear_tabs(self) -> None:
        """Remove all tabs and re-add the + tab."""
        while self.count() > 0:
            self.removeTab(0)
        self._watchlist_ids.clear()
        # Re-add the + tab
        self._add_plus_tab()

    def _rebuild_id_mapping(self) -> None:
        """Rebuild the tab index to watchlist ID mapping after tab removal."""
        # Get current widget -> id mapping
        widget_to_id = {}
        for index, wl_id in self._watchlist_ids.items():
            if index < self.count():
                widget = self.widget(index)
                if widget:
                    widget_to_id[id(widget)] = wl_id

        # Rebuild mapping based on current tab order
        self._watchlist_ids.clear()
        for i in range(self.count()):
            widget = self.widget(i)
            if widget and id(widget) in widget_to_id:
                self._watchlist_ids[i] = widget_to_id[id(widget)]

    def get_tab_content(self, watchlist_id: str) -> Optional[QWidget]:
        """
        Get the content widget for a watchlist tab.

        Args:
            watchlist_id: Watchlist identifier

        Returns:
            Content widget or None if not found
        """
        for index, wl_id in self._watchlist_ids.items():
            if wl_id == watchlist_id:
                return self.widget(index)
        return None
