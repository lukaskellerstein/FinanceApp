"""
Options Chain Page showing real-time option prices for a stock ticker.
Uses Interactive Brokers API for real-time data.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QFrame,
    QSpinBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont

from rx import operators as ops
from rx.disposable import CompositeDisposable

from finance_app.ui.base.base_page import BasePage
from finance_app.ui.windows.main.pages.options_chain.options_chain_service import (
    OptionsChainService,
)

# create logger
log = logging.getLogger("CellarLogger")


class OptionsChainPage(BasePage):
    """
    Options Chain Page showing real-time option prices for a stock ticker.
    Uses Interactive Brokers API for real-time data.
    """

    # Signals for thread-safe UI updates
    updateTableSignal = pyqtSignal(str, float, dict)  # key, strike, data
    updateUnderlyingSignal = pyqtSignal(dict)  # underlying tick data
    chainLoadedSignal = pyqtSignal(dict)  # option chain data
    statusSignal = pyqtSignal(str)  # status message

    def __init__(self, ticker: str = "", *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info(f"Initializing Options Chain Page")

        self.ticker = ticker
        self.service = OptionsChainService()

        # Data storage
        self.option_chain_data: Dict[str, Any] = {}
        self.current_expiration: str = ""
        self.current_strikes: List[float] = []
        self.spot_price: float = 0.0
        self.iv: float = 0.0

        # Option data cache: {strike_right: {field: value}}
        self.options_data: Dict[str, Dict[str, Any]] = {}

        # Track which options have received data
        self.options_with_data: set = set()

        # Timer for marking unavailable options
        self.na_timer: Optional[QTimer] = None

        # Subscriptions
        self.subscriptions = CompositeDisposable()
        self.option_subscriptions: Dict[str, Any] = {}

        # UI setup
        self.initUI()
        self.connectSignals()

    def initUI(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Section
        header_widget = self.create_header_section()
        main_layout.addWidget(header_widget)

        # Options Chain Section
        chain_widget = self.create_chain_section()
        main_layout.addWidget(chain_widget, 1)

        self.setLayout(main_layout)
        self.apply_styles()

    def connectSignals(self):
        """Connect Qt signals for thread-safe UI updates"""
        self.updateTableSignal.connect(self.on_update_table)
        self.updateUnderlyingSignal.connect(self.on_update_underlying)
        self.chainLoadedSignal.connect(self.on_chain_loaded)
        self.statusSignal.connect(self.on_status_update)

    def create_header_section(self) -> QWidget:
        """Create the header section with ticker input and controls"""
        header = QFrame()
        header.setObjectName("headerSection")
        header_layout = QVBoxLayout()
        header_layout.setSpacing(16)
        header_layout.setContentsMargins(24, 24, 24, 24)

        # Row 1: Ticker Input and Load Button
        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        # Ticker Input
        ticker_label = QLabel("Symbol:")
        ticker_label.setFont(QFont("Inter", 13))
        input_row.addWidget(ticker_label)

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Enter ticker (e.g., AAPL)")
        self.ticker_input.setMinimumWidth(120)
        self.ticker_input.setMaximumWidth(150)
        self.ticker_input.setText(self.ticker)
        self.ticker_input.returnPressed.connect(self.load_option_chain)
        input_row.addWidget(self.ticker_input)

        # Load Chain Button
        self.load_button = QPushButton("Load Chain")
        self.load_button.setObjectName("loadButton")
        self.load_button.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        self.load_button.setMinimumWidth(120)
        self.load_button.clicked.connect(self.load_option_chain)
        input_row.addWidget(self.load_button)

        input_row.addSpacing(30)

        # Expiration Dropdown
        exp_label = QLabel("Expiration:")
        exp_label.setFont(QFont("Inter", 13))
        input_row.addWidget(exp_label)

        self.expiration_combo = QComboBox()
        self.expiration_combo.setMinimumWidth(150)
        self.expiration_combo.currentTextChanged.connect(self.on_expiration_changed)
        input_row.addWidget(self.expiration_combo)

        input_row.addSpacing(20)

        # Number of Strikes
        strikes_label = QLabel("Strikes:")
        strikes_label.setFont(QFont("Inter", 13))
        input_row.addWidget(strikes_label)

        self.strikes_spin = QSpinBox()
        self.strikes_spin.setRange(5, 50)
        self.strikes_spin.setValue(11)
        self.strikes_spin.setMinimumWidth(70)
        input_row.addWidget(self.strikes_spin)

        # Refresh Button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setFont(QFont("Inter", 13))
        self.refresh_button.clicked.connect(self.refresh_options_data)
        self.refresh_button.setEnabled(False)
        input_row.addWidget(self.refresh_button)

        input_row.addStretch()
        header_layout.addLayout(input_row)

        # Row 2: Ticker Info Display
        info_row = QHBoxLayout()
        info_row.setSpacing(24)

        # Ticker Symbol
        self.ticker_display = QLabel("--")
        self.ticker_display.setObjectName("tickerSymbol")
        self.ticker_display.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        info_row.addWidget(self.ticker_display)

        info_row.addSpacing(30)

        # Current Price
        price_label_text = QLabel("Last:")
        price_label_text.setObjectName("priceLabel")
        price_label_text.setFont(QFont("Inter", 14))
        info_row.addWidget(price_label_text)

        self.price_display = QLabel("$--")
        self.price_display.setObjectName("currentPrice")
        self.price_display.setFont(QFont("Inter", 24, QFont.Weight.DemiBold))
        info_row.addWidget(self.price_display)

        info_row.addSpacing(20)

        # Bid/Ask
        bid_label = QLabel("Bid:")
        bid_label.setFont(QFont("Inter", 12))
        bid_label.setStyleSheet("color: #a0a0a0;")
        info_row.addWidget(bid_label)

        self.bid_display = QLabel("$--")
        self.bid_display.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        self.bid_display.setStyleSheet("color: #00d26a;")
        info_row.addWidget(self.bid_display)

        ask_label = QLabel("Ask:")
        ask_label.setFont(QFont("Inter", 12))
        ask_label.setStyleSheet("color: #a0a0a0;")
        info_row.addWidget(ask_label)

        self.ask_display = QLabel("$--")
        self.ask_display.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        self.ask_display.setStyleSheet("color: #ff4757;")
        info_row.addWidget(self.ask_display)

        info_row.addSpacing(30)

        # IV Info
        iv_label_text = QLabel("IV:")
        iv_label_text.setObjectName("ivLabel")
        iv_label_text.setFont(QFont("Inter", 14))
        info_row.addWidget(iv_label_text)

        self.iv_display = QLabel("--%")
        self.iv_display.setObjectName("ivValue")
        self.iv_display.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        info_row.addWidget(self.iv_display)

        info_row.addStretch()

        # Status Label
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setFont(QFont("Inter", 11))
        info_row.addWidget(self.status_label)

        header_layout.addLayout(info_row)

        header.setLayout(header_layout)
        return header

    def create_chain_section(self) -> QWidget:
        """Create the options chain table section"""
        chain_widget = QFrame()
        chain_widget.setObjectName("optionsChainSection")
        chain_layout = QVBoxLayout()
        chain_layout.setContentsMargins(24, 24, 24, 24)

        # Table
        self.table = QTableWidget()
        self.table.setObjectName("optionsTable")
        self.table.setColumnCount(15)
        self.table.setHorizontalHeaderLabels([
            "Bid", "Ask", "Last", "IV", "Delta", "Gamma", "Theta", "STRIKE",
            "Theta", "Gamma", "Delta", "IV", "Last", "Ask", "Bid"
        ])

        # Configure table
        self.table.horizontalHeader().setFont(QFont("Inter", 11, QFont.Weight.DemiBold))
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 100)  # Strike column

        chain_layout.addWidget(self.table)
        chain_widget.setLayout(chain_layout)
        return chain_widget

    def load_option_chain(self):
        """Load option chain data for the entered ticker"""
        ticker = self.ticker_input.text().strip().upper()
        if not ticker:
            self.statusSignal.emit("Please enter a ticker symbol")
            return

        self.ticker = ticker
        self.ticker_display.setText(ticker)
        self.statusSignal.emit(f"Loading option chain for {ticker}...")
        self.load_button.setEnabled(False)

        # Clear previous data
        self.clear_subscriptions()
        self.options_data.clear()
        self.table.setRowCount(0)
        self.expiration_combo.clear()

        # Start underlying realtime data
        self.start_underlying_realtime(ticker)

        # Get option chain
        sub = self.service.getOptionChain(ticker).subscribe(
            on_next=lambda x: self.chainLoadedSignal.emit(x),
            on_error=lambda e: self.statusSignal.emit(f"Error: {str(e)}"),
        )
        self.subscriptions.add(sub)

    def start_underlying_realtime(self, ticker: str):
        """Start realtime data for the underlying stock"""
        try:
            realtime_items = self.service.startUnderlyingRealtime(ticker)
            if realtime_items:
                for key, item in realtime_items.items():
                    # Subscribe to ticks
                    sub = item.ticks.subscribe(
                        on_next=lambda x: self.updateUnderlyingSignal.emit(x) if x else None,
                        on_error=lambda e: log.error(f"Underlying tick error: {e}"),
                    )
                    self.subscriptions.add(sub)
        except Exception as e:
            log.error(f"Error starting underlying realtime: {e}")

    def on_chain_loaded(self, data: Dict[str, Any]):
        """Handle option chain data loaded"""
        log.info(f"on_chain_loaded called with data: exchange={data.get('exchange')}, expirations={len(data.get('expirations', []))}, strikes={len(data.get('strikes', []))}")

        if not data or data == {}:
            self.statusSignal.emit("No option chain data received")
            self.load_button.setEnabled(True)
            return

        self.option_chain_data = data
        expirations = data.get("expirations", [])
        strikes = data.get("strikes", [])

        # Filter and sort expirations
        filtered_expirations = self.service.getFilteredExpirations(expirations)
        log.info(f"Filtered expirations: {filtered_expirations[:5]}... (total: {len(filtered_expirations)})")

        # Populate expiration dropdown
        self.expiration_combo.blockSignals(True)
        self.expiration_combo.clear()
        for exp in filtered_expirations:
            # Format expiration date for display
            try:
                exp_date = datetime.strptime(exp, "%Y%m%d")
                display_text = exp_date.strftime("%b %d, %Y")
                self.expiration_combo.addItem(display_text, exp)
            except ValueError:
                self.expiration_combo.addItem(exp, exp)
        self.expiration_combo.blockSignals(False)

        self.statusSignal.emit(f"Loaded {len(filtered_expirations)} expirations, {len(strikes)} strikes")
        self.load_button.setEnabled(True)
        self.refresh_button.setEnabled(True)

        # Auto-select first expiration and manually trigger the change handler
        if filtered_expirations:
            log.info("Auto-selecting first expiration")
            self.expiration_combo.setCurrentIndex(0)
            # Manually call the handler since setCurrentIndex(0) might not trigger signal if already at 0
            self.on_expiration_changed(self.expiration_combo.currentText())

    def on_expiration_changed(self, text: str):
        """Handle expiration selection change"""
        log.info(f"Expiration changed to: {text}")
        if not text:
            return

        # Get the actual expiration code
        idx = self.expiration_combo.currentIndex()
        if idx < 0:
            return

        expiration = self.expiration_combo.itemData(idx)
        if not expiration:
            return

        self.current_expiration = expiration
        self.statusSignal.emit(f"Loading options for {text}...")

        # Clear previous option subscriptions
        self.clear_option_subscriptions()
        self.options_data.clear()

        # Get strikes around current spot price
        all_strikes = self.option_chain_data.get("strikes", [])
        spot = self.spot_price if self.spot_price > 0 else (max(all_strikes) + min(all_strikes)) / 2 if all_strikes else 100

        log.info(f"Spot price: {spot}, all strikes count: {len(all_strikes)}")

        num_strikes = self.strikes_spin.value()
        self.current_strikes = self.service.getFilteredStrikes(all_strikes, spot, num_strikes)

        log.info(f"Filtered strikes: {self.current_strikes}")

        # Setup table
        self.setup_table()

        # Start options realtime
        self.start_options_realtime()

    def setup_table(self):
        """Setup table with current strikes"""
        self.table.setRowCount(len(self.current_strikes))

        for row, strike in enumerate(self.current_strikes):
            # Initialize all cells
            for col in range(15):
                item = QTableWidgetItem("--")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setFont(QFont("Inter", 11))
                self.table.setItem(row, col, item)

            # Set strike column
            strike_item = self.table.item(row, 7)
            strike_item.setText(f"${strike:.2f}")
            strike_item.setFont(QFont("Inter", 11, QFont.Weight.DemiBold))
            strike_item.setBackground(QColor("#2d4a6f"))
            strike_item.setForeground(QColor("#ffffff"))

            # Highlight ATM row
            if self.spot_price > 0 and abs(strike - self.spot_price) == min(abs(s - self.spot_price) for s in self.current_strikes):
                for col in range(15):
                    item = self.table.item(row, col)
                    if item and col != 7:
                        item.setBackground(QColor("#2d4a6f"))

    def start_options_realtime(self):
        """Start realtime data for current options"""
        log.info(f"Starting options realtime - expiration: {self.current_expiration}, strikes: {len(self.current_strikes)}")

        if not self.current_expiration or not self.current_strikes:
            log.warning("No expiration or strikes to stream")
            return

        exchange = self.option_chain_data.get("exchange", "SMART")
        log.info(f"Using exchange: {exchange}")

        # Start realtime for each strike
        options_obs = self.service.startOptionsRealtime(
            symbol=self.ticker,
            expiration=self.current_expiration,
            strikes=self.current_strikes,
            exchange=exchange,
        )

        log.info(f"Got {len(options_obs)} option observables")

        for key, obs in options_obs.items():
            sub = obs.subscribe(
                on_next=lambda data, k=key: self.on_option_tick(k, data),
                on_error=lambda e, k=key: log.error(f"Option tick error for {k}: {e}"),
            )
            self.option_subscriptions[key] = sub

        self.statusSignal.emit(f"Streaming {len(self.current_strikes)} strikes...")

        # Start timer to mark unavailable options after 5 seconds
        if self.na_timer:
            self.na_timer.stop()
        self.na_timer = QTimer()
        self.na_timer.setSingleShot(True)
        self.na_timer.timeout.connect(self.mark_unavailable_options)
        self.na_timer.start(5000)  # 5 seconds

    def mark_unavailable_options(self):
        """Mark options that haven't received any data as N/A"""
        log.info(f"Checking for unavailable options. Received data for {len(self.options_with_data)} options")

        unavailable_count = 0
        for strike in self.current_strikes:
            for option_type in ["C", "P"]:
                key = f"{strike}_{option_type}"
                if key not in self.options_with_data:
                    unavailable_count += 1
                    row = self.current_strikes.index(strike)

                    # Determine columns based on option type
                    if option_type == "C":  # Call - left side
                        cols = [0, 1, 2, 3, 4, 5, 6]  # All call columns
                    else:  # Put - right side
                        cols = [14, 13, 12, 11, 10, 9, 8]  # All put columns

                    # Mark all columns as N/A
                    for col in cols:
                        item = self.table.item(row, col)
                        if item and item.text() == "--":
                            item.setText("N/A")
                            item.setForeground(QColor("#666666"))

        if unavailable_count > 0:
            log.warning(f"{unavailable_count} option contracts have no market data")
            self.statusSignal.emit(f"Streaming... ({unavailable_count} options unavailable)")

    def on_option_tick(self, key: str, data: Dict[str, Any]):
        """Handle option tick data"""
        if not data or data == {}:
            return

        # Parse key to get strike and type
        parts = key.split("_")
        if len(parts) != 2:
            return

        strike = float(parts[0])
        option_type = parts[1]  # "C" or "P"

        # Track that this option received data
        self.options_with_data.add(key)

        # Update cache
        if key not in self.options_data:
            self.options_data[key] = {}
        self.options_data[key].update(data)

        # Emit signal for UI update
        self.updateTableSignal.emit(key, strike, data)

    def on_update_table(self, key: str, strike: float, data: Dict[str, Any]):
        """Update table with new option data (called from main thread)"""
        if strike not in self.current_strikes:
            return

        row = self.current_strikes.index(strike)
        parts = key.split("_")
        option_type = parts[1] if len(parts) == 2 else ""

        # Get full cached data
        cached = self.options_data.get(key, {})

        # Determine columns based on option type
        if option_type == "C":  # Call - left side
            col_bid = 0
            col_ask = 1
            col_last = 2
            col_iv = 3
            col_delta = 4
            col_gamma = 5
            col_theta = 6
        else:  # Put - right side
            col_bid = 14
            col_ask = 13
            col_last = 12
            col_iv = 11
            col_delta = 10
            col_gamma = 9
            col_theta = 8

        # Update cells based on tick type
        tick_type = data.get("tickType", "")

        if "optPrice" in data and data["optPrice"] is not None and data["optPrice"] > 0:
            self.set_cell(row, col_last, f"${data['optPrice']:.2f}", bold=True)

        if "impliedVolatility" in data and data["impliedVolatility"] is not None and data["impliedVolatility"] > 0:
            iv_pct = data["impliedVolatility"] * 100
            self.set_cell(row, col_iv, f"{iv_pct:.1f}%")

        if "delta" in data and data["delta"] is not None:
            delta = data["delta"]
            color = "#00d26a" if option_type == "C" else "#ff4757"
            self.set_cell(row, col_delta, f"{delta:.3f}", color=color)

        if "gamma" in data and data["gamma"] is not None:
            self.set_cell(row, col_gamma, f"{data['gamma']:.4f}")

        if "theta" in data and data["theta"] is not None:
            self.set_cell(row, col_theta, f"{data['theta']:.4f}")

        # Update bid/ask from tick type
        if tick_type == "BID_OPTION_COMPUTATION":
            if "optPrice" in data and data["optPrice"] is not None and data["optPrice"] > 0:
                self.set_cell(row, col_bid, f"${data['optPrice']:.2f}")
        elif tick_type == "ASK_OPTION_COMPUTATION":
            if "optPrice" in data and data["optPrice"] is not None and data["optPrice"] > 0:
                self.set_cell(row, col_ask, f"${data['optPrice']:.2f}")
        elif tick_type == "LAST_OPTION_COMPUTATION":
            if "optPrice" in data and data["optPrice"] is not None and data["optPrice"] > 0:
                self.set_cell(row, col_last, f"${data['optPrice']:.2f}", bold=True)
        elif tick_type == "MODEL_OPTION":
            # Model-based calculation, use for last price
            if "optPrice" in data and data["optPrice"] is not None and data["optPrice"] > 0:
                self.set_cell(row, col_last, f"${data['optPrice']:.2f}", bold=True)

    def set_cell(self, row: int, col: int, value: str, bold: bool = False, color: Optional[str] = None):
        """Set a table cell value"""
        item = self.table.item(row, col)
        if item:
            item.setText(value)
            if bold:
                font = QFont("Inter", 11, QFont.Weight.DemiBold)
                item.setFont(font)
            if color:
                item.setForeground(QColor(color))

    def on_update_underlying(self, data: Dict[str, Any]):
        """Update underlying price display"""
        if not data or data == {}:
            return

        tick_type = data.get("type", "")
        price = data.get("price")

        if tick_type == "last" and price is not None and price > 0:
            self.spot_price = float(price)
            self.price_display.setText(f"${price:.2f}")
        elif tick_type == "bid" and price is not None and price > 0:
            self.bid_display.setText(f"${price:.2f}")
        elif tick_type == "ask" and price is not None and price > 0:
            self.ask_display.setText(f"${price:.2f}")
        elif tick_type == "close" and price is not None and price > 0:
            # Use close as initial spot price if last not available yet
            if self.spot_price <= 0:
                self.spot_price = float(price)
                self.price_display.setText(f"${price:.2f}")
        elif tick_type == "option_implied_vol" and price is not None and price > 0:
            self.iv = float(price)
            self.iv_display.setText(f"{price * 100:.1f}%")

    def on_status_update(self, message: str):
        """Update status label"""
        self.status_label.setText(message)

    def refresh_options_data(self):
        """Refresh the current options data"""
        if self.current_expiration:
            # Trigger expiration change to reload
            self.on_expiration_changed(self.expiration_combo.currentText())

    def clear_option_subscriptions(self):
        """Clear option-specific subscriptions"""
        # Stop the N/A timer
        if self.na_timer:
            self.na_timer.stop()

        # Clear tracking set
        self.options_with_data.clear()

        for key, sub in self.option_subscriptions.items():
            try:
                sub.dispose()
            except Exception as e:
                log.error(f"Error disposing option subscription {key}: {e}")
        self.option_subscriptions.clear()

    def clear_subscriptions(self):
        """Clear all subscriptions"""
        self.clear_option_subscriptions()
        self.subscriptions.dispose()
        self.subscriptions = CompositeDisposable()

    def apply_styles(self):
        """Apply stylesheet to the page"""
        stylesheet = """
            QWidget {
                background-color: #1a1a2e;
                color: #ffffff;
            }

            #headerSection {
                background-color: #16213e;
            }

            #tickerSymbol {
                color: #ffffff;
            }

            #currentPrice {
                color: #ffffff;
            }

            #priceLabel {
                color: #a0a0a0;
            }

            #ivLabel {
                color: #a0a0a0;
            }

            #ivValue {
                color: #4da6ff;
            }

            #statusLabel {
                color: #a0a0a0;
            }

            QLineEdit {
                background-color: #0f3460;
                border: 1px solid #2d3a4f;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-size: 14px;
            }

            QLineEdit:focus {
                border-color: #4da6ff;
            }

            QComboBox {
                background-color: #0f3460;
                border: 1px solid #2d3a4f;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                min-width: 150px;
            }

            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }

            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
            }

            QComboBox QAbstractItemView {
                background-color: #0f3460;
                border: 1px solid #2d3a4f;
                selection-background-color: #4da6ff;
                color: #ffffff;
            }

            QSpinBox {
                background-color: #0f3460;
                border: 1px solid #2d3a4f;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }

            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #2d3a4f;
                border: none;
            }

            #loadButton {
                background-color: #4da6ff;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                color: #ffffff;
            }

            #loadButton:hover {
                background-color: #5eb5ff;
            }

            #loadButton:disabled {
                background-color: #2d3a4f;
                color: #666666;
            }

            #refreshButton {
                background-color: #2d3a4f;
                border: 1px solid #4da6ff;
                border-radius: 4px;
                padding: 8px 16px;
                color: #4da6ff;
            }

            #refreshButton:hover {
                background-color: #3d4a5f;
            }

            #refreshButton:disabled {
                border-color: #2d3a4f;
                color: #666666;
            }

            #optionsChainSection {
                background-color: #1a1a2e;
            }

            #optionsTable {
                background-color: #1a1a2e;
                alternate-background-color: #16213e;
                gridline-color: #2d3a4f;
                border: 1px solid #2d3a4f;
            }

            #optionsTable::item {
                padding: 4px;
            }

            #optionsTable::item:selected {
                background-color: #0f3460;
            }

            QHeaderView::section {
                background-color: #16213e;
                color: #ffffff;
                padding: 8px;
                border: 1px solid #2d3a4f;
                font-weight: bold;
            }
        """
        self.setStyleSheet(stylesheet)

    def onDestroy(self):
        """Cleanup when page is destroyed"""
        log.info("Destroying Options Chain Page")
        self.clear_subscriptions()
        self.service.onDestroy()
        super().onDestroy()
