import logging
import time
from typing import Any, Callable, Optional, Type
from src.ui.windows.asset_detail.shared.pages.contract_details.contract_details import (
    ContractDetailsPage,
)

import rx.operators as ops
from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QMetaObject, Q_ARG
from PyQt6.QtWidgets import QMainWindow

from src.business.model.asset import Asset, AssetType
from src.business.model.contracts import IBStockContract
from src.business.model.timeframe import TimeFrame
from src.business.modules.asset_bl import AssetBL
from src.ui.base.base_page import BasePage
from src.ui.windows.asset_detail.shared.pages.basic_info.basic_info import (
    BasicInfoPage,
)
from src.ui.windows.asset_detail.shared.pages.history_chart.history_chart import (
    HistoryChartPage,
)
from src.ui.windows.asset_detail.shared.pages.history_table.history_table import (
    HistoryTablePage,
)

# create logger
log = logging.getLogger("CellarLogger")


class AssetDetailWindow(QMainWindow):
    asset: Asset

    currentPage: BasePage

    on_update = pyqtSignal()
    price_updated = pyqtSignal(float, float, float)  # price, change, change_pct

    def __init__(self, asset: Asset):
        super().__init__()

        # load template
        uic.loadUi(
            "src/ui/windows/asset_detail/shared/asset_detail_window.ui", self
        )

        # load styles
        with open(
            "src/ui/windows/asset_detail/shared/asset_detail_window.qss", "r"
        ) as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.asset = asset

        # Business logic
        self.__bl = AssetBL()
        self.__realtimeSubscription = None
        self.__previousClose: Optional[float] = None

        # Connect price update signal to UI update slot
        self.price_updated.connect(self.__updatePriceDisplay)

        self.fillHeaderBar()
        self.__loadPreviousClose()
        self.__startRealtimeData()

        # MenuBar actions
        self.actionBasicInfo.triggered.connect(
            self.setCurrentPage(BasicInfoPage, data=self.asset)
        )
        self.actionTable.triggered.connect(
            self.setCurrentPage(HistoryTablePage, asset=self.asset)
        )
        self.actionChart.triggered.connect(
            self.setCurrentPage(HistoryChartPage, asset=self.asset)
        )
        self.actionContractDetails.triggered.connect(
            self.setCurrentPage(ContractDetailsPage, asset=self.asset)
        )

        # Stacket Widget
        self.pageBox.removeWidget(self.pageBox.widget(0))
        self.pageBox.removeWidget(self.pageBox.widget(0))

        self.currentPage = None
        self.setCurrentPage(HistoryChartPage, asset=self.asset)()

    def fillHeaderBar(self):
        self.secTypeLabel.setText(self.asset.type)
        self.symbolLabel.setText(f"{self.asset.symbol} - {self.asset.shortDescription}")
        self.setWindowTitle(
            f"{self.asset.symbol} - {self.asset.shortDescription}"
        )
        # Initialize price labels
        self.priceLabel.setText("--")
        self.changeLabel.setText("--")

    def __loadPreviousClose(self):
        """Load the previous close price from historical data to calculate change"""
        try:
            histData = self.__bl.getHistoricalDataFromDB(self.asset.symbol, TimeFrame.day1)
            if histData is not None and len(histData) >= 2:
                # Get the second to last close price (previous day's close)
                self.__previousClose = histData.iloc[-2]["Close"]
                log.info(f"Previous close for {self.asset.symbol}: {self.__previousClose}")
        except Exception as e:
            log.warning(f"Error loading previous close for {self.asset.symbol}: {e}")

    def __startRealtimeData(self):
        """Start realtime data subscription for the asset"""
        if not self.asset.contractDetails:
            log.warning(f"No contract details for {self.asset.symbol}")
            return

        contract = self.asset.contractDetails[0].contract
        log.info(f"Starting realtime data for {self.asset.symbol}")

        try:
            self.__realtimeSubscription = self.__bl.startRealtime(contract).subscribe(
                on_next=self.__onRealtimeData,
                on_error=lambda e: log.error(f"Realtime data error: {e}"),
            )
        except Exception as e:
            log.error(f"Error starting realtime data for {self.asset.symbol}: {e}")

    def __onRealtimeData(self, data: Any):
        """Handle incoming realtime data"""
        if data is None:
            return

        try:
            # Data structure from IB: {"ticker": symbol, "localSymbol": ..., "type": tick_type, "price": value}
            # We're interested in "last" price type for current price display
            if isinstance(data, dict):
                tick_type = data.get("type", "").lower()
                price_value = data.get("price")

                # Only update display for "last" price (actual trade price)
                # Other types: bid, ask, close, open, high, low, volume, etc.
                if tick_type == "last" and price_value is not None and price_value > 0:
                    change = 0.0
                    change_pct = 0.0

                    if self.__previousClose and self.__previousClose > 0:
                        change = price_value - self.__previousClose
                        change_pct = (change / self.__previousClose) * 100

                    # Emit signal to update UI on main thread
                    self.price_updated.emit(float(price_value), change, change_pct)

                # Also handle "close" if market is closed
                elif tick_type == "close" and price_value is not None and price_value > 0:
                    change = 0.0
                    change_pct = 0.0

                    if self.__previousClose and self.__previousClose > 0:
                        change = price_value - self.__previousClose
                        change_pct = (change / self.__previousClose) * 100

                    self.price_updated.emit(float(price_value), change, change_pct)

        except Exception as e:
            log.warning(f"Error processing realtime data: {e}")

    @pyqtSlot(float, float, float)
    def __updatePriceDisplay(self, price: float, change: float, change_pct: float):
        """Update the price display labels (runs on main thread)"""
        self.priceLabel.setText(f"${price:.2f}")

        # Format change text
        sign = "+" if change >= 0 else ""
        self.changeLabel.setText(f"{sign}{change:.2f} ({sign}{change_pct:.2f}%)")

        # Update style based on positive/negative
        if change >= 0:
            self.changeLabel.setProperty("positive", True)
            self.changeLabel.setProperty("negative", False)
        else:
            self.changeLabel.setProperty("positive", False)
            self.changeLabel.setProperty("negative", True)

        # Force style refresh
        self.changeLabel.style().unpolish(self.changeLabel)
        self.changeLabel.style().polish(self.changeLabel)

    # def __pageOnUpdate(self):
    #     self.on_update.emit()

    # --------------
    # HOF - High Ordered Function -> returns function
    # --------------
    def setCurrentPage(
        self, page: Type[BasePage], **kwargs: Any
    ) -> Callable[[], None]:
        def setPage():
            if self.currentPage is not None:
                self.pageBox.removeWidget(self.currentPage)
                self.currentPage.onDestroy()

            if kwargs is not None:
                self.currentPage = page(**kwargs)
            else:
                self.currentPage = page()

            self.currentPage.on_update.connect(self.on_update.emit)
            self.pageBox.addWidget(self.currentPage)
            self.pageBox.setCurrentIndex(0)

        return setPage

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    def __stopRealtimeData(self):
        """Stop realtime data subscription"""
        if self.__realtimeSubscription is not None:
            try:
                self.__realtimeSubscription.dispose()
                log.info(f"Stopped realtime data for {self.asset.symbol}")
            except Exception as e:
                log.warning(f"Error stopping realtime data: {e}")
            self.__realtimeSubscription = None

        if self.asset.contractDetails:
            contract = self.asset.contractDetails[0].contract
            try:
                self.__bl.stopRealtime(contract)
            except Exception as e:
                log.warning(f"Error stopping realtime via BL: {e}")

    # Qt destroy -----------------------------------------
    def closeEvent(self, event: Any):
        log.info("Running ...")
        self.__stopRealtimeData()
        self.currentPage.onDestroy()
        self.__bl.onDestroy()

    # 1. CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")
        self.__stopRealtimeData()
        self.currentPage.onDestroy()
        self.__bl.onDestroy()

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
