"""
Asset Detail Window - displays detailed information about an asset.

Adapted from the old src/ui/windows/asset_detail/shared/asset_detail_window.py
to work with the new Clean Architecture.
"""

import json
import logging
import math
import os
import subprocess
import webbrowser
from typing import Any, Callable, Optional, Type

import numpy as np
from PyQt6 import uic
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QMainWindow, QWidget

from src.application.bootstrap import get_app
from src.domain.entities.asset import Asset, AssetType
from src.domain.entities.timeframe import TimeFrame
from src.presentation.core.base_view import BaseView
from src.presentation.windows.asset_detail.pages.history_chart.history_chart import (
    HistoryChartPage,
)
from src.presentation.windows.asset_detail.pages.history_table.history_table import (
    HistoryTablePage,
)
from src.presentation.windows.asset_detail.pages.future_history_chart.future_history_chart import (
    FutureHistoryChartPage,
)
from src.presentation.windows.asset_detail.pages.future_history_table.future_history_table import (
    FutureHistoryTablePage,
)
from src.presentation.windows.asset_detail.pages.fundamentals.info.info_page import (
    InfoPage,
)
from src.presentation.windows.asset_detail.pages.fundamentals.calendar.calendar_page import (
    CalendarPage,
)
from src.presentation.windows.asset_detail.dialogs.manage_contracts_dialog import (
    ManageContractsDialog,
)

log = logging.getLogger("CellarLogger")


class AssetDetailWindow(QMainWindow):
    """
    Window for displaying asset details.

    Features:
    - Header with asset type and symbol
    - Menu navigation between Table and Chart pages
    - Stacked widget for page switching
    """

    asset: Asset
    currentPage: Optional[BaseView]

    on_update = pyqtSignal()

    def __init__(self, asset: Asset, parent: Optional[QWidget] = None):
        # Don't pass parent to make this a normal independent window
        super().__init__()

        self.asset = asset
        self.currentPage = None
        self._parent_window = parent  # Store for workspace management

        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Load template
        ui_path = os.path.join(current_dir, "asset_detail_window.ui")
        uic.loadUi(ui_path, self)

        # Load styles
        qss_path = os.path.join(current_dir, "asset_detail_window.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r") as fh:
                self.setStyleSheet(fh.read())

        # Apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self._fill_header_bar()

        # Determine which pages to use based on asset type
        is_future = self.asset.asset_type == AssetType.FUTURE

        # MenuBar actions - Data menu
        # Use futures-specific pages for futures, standard pages for other assets
        TablePage = FutureHistoryTablePage if is_future else HistoryTablePage
        ChartPage = FutureHistoryChartPage if is_future else HistoryChartPage

        self.actionTable.triggered.connect(
            self.setCurrentPage(TablePage, asset=self.asset)
        )
        self.actionChart.triggered.connect(
            self.setCurrentPage(ChartPage, asset=self.asset)
        )

        # MenuBar actions - Fundamentals menu
        self.actionInfo.triggered.connect(
            self.setCurrentPage(InfoPage, asset=self.asset)
        )
        self.actionCalendar.triggered.connect(
            self.setCurrentPage(CalendarPage, asset=self.asset)
        )

        # MenuBar actions - Contracts menu (futures only)
        self._setup_contracts_menu()

        # MenuBar actions - External data sources (stocks only)
        self._setup_yahoo_finance_menu()
        self._setup_nasdaq_menu()
        self._setup_marketwatch_menu()

        # Stacked Widget - remove and delete default placeholder pages
        while self.pageBox.count():
            widget = self.pageBox.widget(0)
            self.pageBox.removeWidget(widget)
            widget.deleteLater()

        # Set default page to Chart (use futures-specific page for futures)
        self.setCurrentPage(ChartPage, asset=self.asset)()

    def _fill_header_bar(self) -> None:
        """Fill the header bar with asset information."""
        # Set symbol
        self.symbolLabel.setText(self.asset.symbol)

        # Get description for window title
        description = self.asset.short_description or ""
        if not description and self.asset.contract_details:
            cd = self.asset.contract_details[0]
            if hasattr(cd, 'long_name') and cd.long_name:
                description = cd.long_name

        self.setWindowTitle(f"{self.asset.symbol} - {description}")

        # Get historical data to calculate price and change
        app = get_app()
        data = app.historical_data_service.get_historical_data(
            self.asset.symbol, TimeFrame.DAY_1.value
        )

        if data is not None and len(data) >= 2:
            data = data.sort_index()
            # Get last two days
            last_close = data['Close'].iloc[-1]
            prev_close = data['Close'].iloc[-2]

            # Calculate change
            change = last_close - prev_close
            change_pct = (change / prev_close) * 100 if prev_close != 0 else 0

            # Set price label
            self.priceLabel.setText(f"${last_close:,.2f}")

            # Set change label with color
            change_sign = "+" if change >= 0 else ""
            self.changeLabel.setText(f"{change_sign}${change:,.2f} ({change_sign}{change_pct:.2f}%)")

            # Set color based on change direction
            if change >= 0:
                self.changeLabel.setStyleSheet("color: #22c55e; font-size: 14px;")  # Green
            else:
                self.changeLabel.setStyleSheet("color: #ef4444; font-size: 14px;")  # Red

            # Calculate Historical Volatility (20-day annualized)
            if len(data) >= 20:
                returns = np.log(data['Close'] / data['Close'].shift(1)).dropna()
                hv = returns.tail(20).std() * math.sqrt(252) * 100  # Annualized
                self.hvLabel.setText(f"HV: {hv:.1f}%")
            else:
                self.hvLabel.setText("HV: --")

            # IV would come from options data - show placeholder for now
            self.ivLabel.setText("IV: --")

        elif data is not None and len(data) == 1:
            last_close = data['Close'].iloc[-1]
            self.priceLabel.setText(f"${last_close:,.2f}")
            self.changeLabel.setText("$0.00 (0.00%)")
            self.changeLabel.setStyleSheet("color: #9ca3af; font-size: 14px;")
            self.ivLabel.setText("IV: --")
            self.hvLabel.setText("HV: --")
        else:
            self.priceLabel.setText("$--")
            self.changeLabel.setText("No data")
            self.changeLabel.setStyleSheet("color: #9ca3af; font-size: 14px;")
            self.ivLabel.setText("IV: --")
            self.hvLabel.setText("HV: --")

    def _setup_contracts_menu(self) -> None:
        """Setup Contracts menu - visible only for futures."""
        is_future = self.asset.asset_type == AssetType.FUTURE

        # Connect action to open dialog
        self.actionManageContracts.triggered.connect(self._open_manage_contracts_dialog)

        # Show/hide menu based on asset type
        self.menuContracts.menuAction().setVisible(is_future)

    def _open_manage_contracts_dialog(self) -> None:
        """Open the Manage Contracts dialog."""
        dialog = ManageContractsDialog(self.asset, self)
        dialog.contracts_changed.connect(self._on_contracts_changed)
        dialog.exec()

    def _on_contracts_changed(self) -> None:
        """Handle contracts being added or removed."""
        log.info("Contracts changed, refreshing asset data...")
        # Reload asset from repository to get updated contracts
        app = get_app()
        updated_asset = app.asset_service.get_asset(
            self.asset.asset_type.value, self.asset.symbol
        )
        if updated_asset:
            self.asset = updated_asset
            # Refresh current page if it has a refresh method
            if self.currentPage is not None and hasattr(self.currentPage, 'refresh'):
                self.currentPage.refresh(self.asset)
        # Emit update signal so pages can refresh
        self.on_update.emit()

    def _setup_yahoo_finance_menu(self) -> None:
        """Setup Yahoo Finance menu items - visible only for stocks."""
        symbol = self.asset.symbol.upper()

        # Define Yahoo Finance URLs
        urls = {
            "earnings": f"https://finance.yahoo.com/quote/{symbol}/analysis",
            "dividends": f"https://finance.yahoo.com/quote/{symbol}/history?filter=div",
            "splits": f"https://finance.yahoo.com/quote/{symbol}/history?filter=split",
            "all_events": f"https://finance.yahoo.com/quote/{symbol}/",
        }

        # Connect actions to open URLs in browser
        self.actionYFEarnings.triggered.connect(
            lambda: webbrowser.open(urls["earnings"])
        )
        self.actionYFDividends.triggered.connect(
            lambda: webbrowser.open(urls["dividends"])
        )
        self.actionYFSplits.triggered.connect(
            lambda: webbrowser.open(urls["splits"])
        )
        self.actionYFAllEvents.triggered.connect(
            lambda: webbrowser.open(urls["all_events"])
        )

        # Hide the entire Yahoo Finance menu for non-stock assets
        is_stock = self.asset.asset_type == AssetType.STOCK
        self.menuYahooFinance.menuAction().setVisible(is_stock)

    def _setup_nasdaq_menu(self) -> None:
        """Setup Nasdaq menu items - visible only for stocks."""
        symbol = self.asset.symbol.lower()

        # Define Nasdaq URLs
        urls = {
            "news": f"https://www.nasdaq.com/market-activity/stocks/{symbol}/news-headlines",
            "earnings": f"https://www.nasdaq.com/market-activity/stocks/{symbol}/earnings",
            "dividends": f"https://www.nasdaq.com/market-activity/stocks/{symbol}/dividend-history",
        }

        # Connect actions to open URLs in browser
        self.actionNasdaqNews.triggered.connect(
            lambda: webbrowser.open(urls["news"])
        )
        self.actionNasdaqEarnings.triggered.connect(
            lambda: webbrowser.open(urls["earnings"])
        )
        self.actionNasdaqDividends.triggered.connect(
            lambda: webbrowser.open(urls["dividends"])
        )

        # Hide the entire Nasdaq menu for non-stock assets
        is_stock = self.asset.asset_type == AssetType.STOCK
        self.menuNasdaq.menuAction().setVisible(is_stock)

    def _setup_marketwatch_menu(self) -> None:
        """Setup MarketWatch menu items - visible only for stocks."""
        symbol = self.asset.symbol.lower()

        # Define MarketWatch URLs
        urls = {
            "profile": f"https://www.marketwatch.com/investing/stock/{symbol}/company-profile",
            "income": f"https://www.marketwatch.com/investing/stock/{symbol}/financials",
            "balance_sheet": f"https://www.marketwatch.com/investing/stock/{symbol}/financials/balance-sheet",
            "cash_flow": f"https://www.marketwatch.com/investing/stock/{symbol}/financials/cash-flow",
            "all_reports": f"https://www.marketwatch.com/investing/stock/{symbol}/financials/secfilings",
            "analyst_estimates": f"https://www.marketwatch.com/investing/stock/{symbol}/analystestimates",
        }

        # Connect actions to open URLs in browser
        self.actionMWProfile.triggered.connect(
            lambda: webbrowser.open(urls["profile"])
        )
        self.actionMWIncome.triggered.connect(
            lambda: webbrowser.open(urls["income"])
        )
        self.actionMWBalanceSheet.triggered.connect(
            lambda: webbrowser.open(urls["balance_sheet"])
        )
        self.actionMWCashFlow.triggered.connect(
            lambda: webbrowser.open(urls["cash_flow"])
        )
        self.actionMWAllReports.triggered.connect(
            lambda: webbrowser.open(urls["all_reports"])
        )
        self.actionMWAnalystEstimates.triggered.connect(
            lambda: webbrowser.open(urls["analyst_estimates"])
        )

        # Hide the entire MarketWatch menu for non-stock assets
        is_stock = self.asset.asset_type == AssetType.STOCK
        self.menuMarketWatch.menuAction().setVisible(is_stock)

    def setCurrentPage(
        self, page: Type[BaseView], **kwargs: Any
    ) -> Callable[[], None]:
        """
        Higher-Order Function for page navigation.

        Returns a function that switches to the specified page.
        This pattern allows use with Qt signal connections.

        Args:
            page: The page class to instantiate
            **kwargs: Arguments to pass to page constructor

        Returns:
            Function that performs the page switch
        """
        def set_page() -> None:
            if self.currentPage is not None:
                self.pageBox.removeWidget(self.currentPage)
                self.currentPage.onDestroy()
                self.currentPage.deleteLater()

            if kwargs:
                self.currentPage = page(**kwargs)
            else:
                self.currentPage = page()

            if hasattr(self.currentPage, 'on_update'):
                self.currentPage.on_update.connect(self.on_update.emit)
            self.pageBox.addWidget(self.currentPage)
            self.pageBox.setCurrentIndex(0)

        return set_page

    # --------------------------------------------------------
    # WORKSPACE MANAGEMENT (for i3wm/Regolith)
    # --------------------------------------------------------

    def show(self) -> None:
        """Override show to move window to parent's workspace in i3wm."""
        super().show()

        # Schedule workspace move after window is fully shown
        if self._parent_window is not None:
            QTimer.singleShot(100, self._move_to_parent_workspace)

    def _move_to_parent_workspace(self) -> None:
        """Move this window to the same workspace as the parent window."""
        if self._parent_window is None:
            return

        parent_workspace = self._get_window_workspace(self._parent_window.windowTitle())
        if parent_workspace is not None:
            self._move_to_workspace(parent_workspace)

    def _get_window_workspace(self, window_title: str) -> Optional[int]:
        """Get the workspace number for a window by its title."""
        try:
            result = subprocess.run(
                ["i3-msg", "-t", "get_tree"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return None

            tree = json.loads(result.stdout)

            def find_workspace(node, current_workspace=None):
                # Track current workspace as we descend
                if node.get("type") == "workspace":
                    current_workspace = node.get("num")

                # Check if this node is our window
                title = node.get('window_properties', {}).get('title', '')
                if title == window_title:
                    return current_workspace

                # Recursively search children
                for child in node.get('nodes', []) + node.get('floating_nodes', []):
                    found = find_workspace(child, current_workspace)
                    if found is not None:
                        return found
                return None

            return find_workspace(tree)
        except Exception as e:
            log.debug(f"Could not get workspace for window: {e}")
            return None

    def _get_this_window_con_id(self) -> Optional[int]:
        """Get the i3 container ID for this window."""
        try:
            result = subprocess.run(
                ["i3-msg", "-t", "get_tree"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return None

            tree = json.loads(result.stdout)
            window_title = self.windowTitle()

            def find_con_id(node):
                title = node.get('window_properties', {}).get('title', '')
                if title == window_title:
                    return node.get('id')
                for child in node.get('nodes', []) + node.get('floating_nodes', []):
                    found = find_con_id(child)
                    if found:
                        return found
                return None

            return find_con_id(tree)
        except Exception as e:
            log.debug(f"Could not get con_id for window: {e}")
            return None

    def _move_to_workspace(self, workspace: int) -> bool:
        """Move this window to the specified workspace using i3-msg."""
        try:
            con_id = self._get_this_window_con_id()
            if con_id is None:
                log.debug("Could not find con_id for this window")
                return False

            result = subprocess.run(
                ["i3-msg", f"[con_id={con_id}] move container to workspace number {workspace}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                log.debug(f"Moved window to workspace {workspace}")
                return True
            else:
                log.debug(f"Failed to move window: {result.stderr}")
                return False
        except Exception as e:
            log.debug(f"Could not move window to workspace: {e}")
            return False

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def closeEvent(self, event: Any) -> None:
        """Qt close event handler."""
        log.info("AssetDetailWindow closing...")
        if self.currentPage is not None:
            self.currentPage.onDestroy()
        event.accept()

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("AssetDetailWindow destroying...")
        if self.currentPage is not None:
            self.currentPage.onDestroy()

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("AssetDetailWindow deleted")
