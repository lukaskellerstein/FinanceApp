import logging
from datetime import date, datetime, timedelta
from typing import Optional
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
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from finance_app.ui.base.base_page import BasePage
from finance_app.business.modules.options_pricing import OptionsPricingCalculator

# create logger
log = logging.getLogger("CellarLogger")


class OptionsChainPage(BasePage):
    """
    Options Chain Page showing theoretical option prices for a stock ticker.
    Uses QuantLib Black-Scholes model for pricing calculations.
    """

    def __init__(self, ticker: str = "AAPL", *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info(f"Initializing Options Chain Page for {ticker}")

        self.ticker = ticker
        self.calculator = OptionsPricingCalculator()
        self.spot_price = 178.72
        self.volatility = 0.245  # 24.5%
        self.risk_free_rate = 0.045  # 4.5%
        self.dividend_yield = 0.005  # 0.5%

        self.initUI()
        self.load_options_chain()

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
        main_layout.addWidget(chain_widget, 1)  # Give it stretch factor

        self.setLayout(main_layout)
        self.apply_styles()

    def create_header_section(self) -> QWidget:
        """Create the header section with ticker info and controls"""
        header = QFrame()
        header.setObjectName("headerSection")
        header_layout = QVBoxLayout()
        header_layout.setSpacing(16)
        header_layout.setContentsMargins(24, 24, 24, 24)

        # Ticker Row
        ticker_row = QHBoxLayout()
        ticker_row.setSpacing(24)

        # Ticker Symbol and Company Name
        ticker_label = QLabel(self.ticker)
        ticker_label.setObjectName("tickerSymbol")
        ticker_label.setFont(QFont("Inter", 32, QFont.Weight.Bold))
        ticker_row.addWidget(ticker_label)

        company_label = QLabel("Apple Inc.")
        company_label.setObjectName("companyName")
        company_label.setFont(QFont("Inter", 18))
        ticker_row.addWidget(company_label)

        ticker_row.addSpacing(50)

        # Current Price
        price_label = QLabel(f"${self.spot_price:.2f}")
        price_label.setObjectName("currentPrice")
        price_label.setFont(QFont("Inter", 28, QFont.Weight.DemiBold))
        ticker_row.addWidget(price_label)

        # Price Change (mock data)
        change_frame = QFrame()
        change_frame.setObjectName("priceChange")
        change_layout = QHBoxLayout()
        change_layout.setContentsMargins(6, 4, 6, 4)
        change_label = QLabel("+$2.34 (+1.33%)")
        change_label.setObjectName("changeValue")
        change_label.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        change_layout.addWidget(change_label)
        change_frame.setLayout(change_layout)
        ticker_row.addWidget(change_frame)

        ticker_row.addSpacing(30)

        # IV Info
        iv_label_text = QLabel("IV:")
        iv_label_text.setObjectName("ivLabel")
        iv_label_text.setFont(QFont("Inter", 14))
        ticker_row.addWidget(iv_label_text)

        iv_value = QLabel(f"{self.volatility * 100:.1f}%")
        iv_value.setObjectName("ivValue")
        iv_value.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        ticker_row.addWidget(iv_value)

        ticker_row.addStretch()
        header_layout.addLayout(ticker_row)

        # Controls Row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(12)

        # Spot Price Input
        spot_label = QLabel("Spot Price:")
        spot_label.setFont(QFont("Inter", 13))
        controls_row.addWidget(spot_label)

        self.spot_input = QDoubleSpinBox()
        self.spot_input.setRange(0, 10000)
        self.spot_input.setValue(self.spot_price)
        self.spot_input.setDecimals(2)
        self.spot_input.setMinimumWidth(100)
        controls_row.addWidget(self.spot_input)

        # Volatility Input
        vol_label = QLabel("IV (%):")
        vol_label.setFont(QFont("Inter", 13))
        controls_row.addWidget(vol_label)

        self.vol_input = QDoubleSpinBox()
        self.vol_input.setRange(0, 200)
        self.vol_input.setValue(self.volatility * 100)
        self.vol_input.setDecimals(2)
        self.vol_input.setMinimumWidth(100)
        controls_row.addWidget(self.vol_input)

        # Risk-Free Rate Input
        rate_label = QLabel("Risk-Free Rate (%):")
        rate_label.setFont(QFont("Inter", 13))
        controls_row.addWidget(rate_label)

        self.rate_input = QDoubleSpinBox()
        self.rate_input.setRange(0, 20)
        self.rate_input.setValue(self.risk_free_rate * 100)
        self.rate_input.setDecimals(2)
        self.rate_input.setMinimumWidth(100)
        controls_row.addWidget(self.rate_input)

        # Expiration Date Input
        exp_label = QLabel("Expiration:")
        exp_label.setFont(QFont("Inter", 13))
        controls_row.addWidget(exp_label)

        self.exp_input = QDateEdit()
        self.exp_input.setCalendarPopup(True)
        exp_date = date.today() + timedelta(days=45)
        self.exp_input.setDate(QDate(exp_date.year, exp_date.month, exp_date.day))
        self.exp_input.setMinimumWidth(120)
        controls_row.addWidget(self.exp_input)

        # Calculate Button
        calc_button = QPushButton("Calculate")
        calc_button.setObjectName("calculateButton")
        calc_button.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        calc_button.setMinimumWidth(100)
        calc_button.clicked.connect(self.load_options_chain)
        controls_row.addWidget(calc_button)

        controls_row.addStretch()
        header_layout.addLayout(controls_row)

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
        self.table.setColumnCount(13)
        self.table.setHorizontalHeaderLabels([
            "Bid", "Ask", "Last", "Volume", "OI", "Delta", "STRIKE",
            "Delta", "OI", "Volume", "Last", "Ask", "Bid"
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
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 100)  # Strike column

        chain_layout.addWidget(self.table)
        chain_widget.setLayout(chain_layout)
        return chain_widget

    def load_options_chain(self):
        """Load and display options chain data"""
        try:
            # Get input values
            spot_price = self.spot_input.value()
            volatility = self.vol_input.value() / 100
            risk_free_rate = self.rate_input.value() / 100
            exp_qdate = self.exp_input.date()
            expiration_date = date(exp_qdate.year(), exp_qdate.month(), exp_qdate.day())

            # Generate strike prices
            strike_prices = self.calculator.generate_strike_prices(
                spot_price, num_strikes=11, strike_interval_pct=2.5
            )

            # Calculate options chain
            chain_data = self.calculator.calculate_options_chain(
                spot_price=spot_price,
                strike_prices=strike_prices,
                risk_free_rate=risk_free_rate,
                volatility=volatility,
                expiration_date=expiration_date,
                dividend_yield=self.dividend_yield,
            )

            # Populate table
            self.table.setRowCount(len(chain_data))

            for row, option_data in enumerate(chain_data):
                strike = option_data["strike"]
                call = option_data["call"]
                put = option_data["put"]
                is_atm = option_data["is_atm"]

                # Call side (left)
                self.set_table_item(row, 0, f"${call['price'] * 0.98:.2f}")  # Bid (mock)
                self.set_table_item(row, 1, f"${call['price'] * 1.02:.2f}")  # Ask (mock)
                self.set_table_item(row, 2, f"${call['price']:.2f}", is_bold=True)  # Last
                self.set_table_item(row, 3, "150")  # Volume (mock)
                self.set_table_item(row, 4, "1,234")  # OI (mock)
                self.set_table_item(row, 5, f"{call['delta']:.3f}", color="#00d26a")  # Delta

                # Strike (center)
                self.set_table_item(row, 6, f"${strike:.1f}", is_bold=True, is_strike=True, is_atm=is_atm)

                # Put side (right)
                self.set_table_item(row, 7, f"{put['delta']:.3f}", color="#ff4757")  # Delta
                self.set_table_item(row, 8, "987")  # OI (mock)
                self.set_table_item(row, 9, "89")  # Volume (mock)
                self.set_table_item(row, 10, f"${put['price']:.2f}", is_bold=True)  # Last
                self.set_table_item(row, 11, f"${put['price'] * 1.02:.2f}")  # Ask (mock)
                self.set_table_item(row, 12, f"${put['price'] * 0.98:.2f}")  # Bid (mock)

                # Highlight ATM row
                if is_atm:
                    for col in range(13):
                        item = self.table.item(row, col)
                        if item:
                            item.setBackground(QColor("#2d4a6f"))

            log.info(f"Loaded options chain with {len(chain_data)} strikes")

        except Exception as e:
            log.error(f"Error loading options chain: {e}")

    def set_table_item(
        self,
        row: int,
        col: int,
        value: str,
        is_bold: bool = False,
        is_strike: bool = False,
        is_atm: bool = False,
        color: Optional[str] = None,
    ):
        """Set a table item with formatting"""
        item = QTableWidgetItem(value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        font = QFont("Inter", 11)
        if is_bold or is_strike:
            font.setWeight(QFont.Weight.DemiBold)
        item.setFont(font)

        if color:
            item.setForeground(QColor(color))

        if is_strike:
            item.setBackground(QColor("#2d4a6f"))
            item.setForeground(QColor("#ffffff"))

        self.table.setItem(row, col, item)

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

            #companyName {
                color: #a0a0a0;
            }

            #currentPrice {
                color: #ffffff;
            }

            #priceChange {
                background-color: #1a3a2e;
                border-radius: 4px;
            }

            #changeValue {
                color: #00d26a;
            }

            #ivLabel {
                color: #a0a0a0;
            }

            #ivValue {
                color: #4da6ff;
            }

            QDoubleSpinBox, QDateEdit {
                background-color: #0f3460;
                border: 1px solid #2d3a4f;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }

            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
            QDateEdit::up-button, QDateEdit::down-button {
                background-color: #2d3a4f;
                border: none;
            }

            #calculateButton {
                background-color: #4da6ff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                color: #ffffff;
            }

            #calculateButton:hover {
                background-color: #5eb5ff;
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
        super().onDestroy()
