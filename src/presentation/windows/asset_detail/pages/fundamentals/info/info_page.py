"""
Info Page - displays contract details and asset information.

Shows all IB contract details for the asset in an organized layout.
"""

import logging
import os
from typing import Any, List, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.domain.entities.asset import Asset
from src.presentation.core.base_view import BaseView

log = logging.getLogger("CellarLogger")


class InfoPage(BaseView):
    """
    Page for displaying asset contract details.

    Shows all IB data for the asset organized in sections:
    - Basic Info
    - Contract Details
    - Industry Classification
    - Trading Info
    - Time & Hours
    """

    # Tell BaseView where to find UI/QSS files
    ui_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "info_page.ui")
    qss_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "info_page.qss")

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("InfoPage initializing...")

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]

        # Build the info display
        self._build_info_display()

    def _build_info_display(self) -> None:
        """Build the info display with contract details."""
        # Get the content layout from the scroll area
        content_layout = self.contentLayout

        # Remove the placeholder label and spacer
        while content_layout.count():
            item = content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Check if we have contract details
        if not self.asset.contract_details:
            no_data = QLabel("No contract details available for this asset.")
            no_data.setObjectName("noDataLabel")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_layout.addWidget(no_data)
            content_layout.addStretch()
            return

        # Get the first contract details (most relevant)
        cd = self.asset.contract_details[0]
        contract = cd.contract if hasattr(cd, 'contract') else None

        # Basic Info Section
        basic_fields = [
            ("Symbol", self.asset.symbol),
            ("Long Name", getattr(cd, 'long_name', '') or ''),
            ("Security Type", getattr(contract, 'sec_type', '') if contract else ''),
            ("Currency", getattr(contract, 'currency', '') if contract else ''),
            ("Primary Exchange", getattr(contract, 'primary_exchange', '') if contract else ''),
            ("Exchange", getattr(contract, 'exchange', '') if contract else ''),
        ]
        self._add_section("Basic Information", basic_fields, content_layout)

        # Contract Details Section
        contract_fields = [
            ("Contract ID", str(getattr(contract, 'con_id', '')) if contract else ''),
            ("Local Symbol", getattr(contract, 'local_symbol', '') if contract else ''),
            ("Trading Class", getattr(contract, 'trading_class', '') if contract else ''),
            ("Market Name", getattr(cd, 'market_name', '')),
            ("Stock Type", getattr(cd, 'stock_type', '')),
        ]
        self._add_section("Contract Details", contract_fields, content_layout)

        # Industry Classification Section
        industry_fields = [
            ("Industry", getattr(cd, 'industry', '')),
            ("Category", getattr(cd, 'category', '')),
            ("Subcategory", getattr(cd, 'subcategory', '')),
        ]
        self._add_section("Industry Classification", industry_fields, content_layout)

        # Trading Info Section
        trading_fields = [
            ("Min Tick", str(getattr(cd, 'min_tick', ''))),
            ("Min Size", str(getattr(cd, 'min_size', ''))),
            ("Size Increment", str(getattr(cd, 'size_increment', ''))),
            ("Price Magnifier", str(getattr(cd, 'price_magnifier', ''))),
            ("Valid Exchanges", getattr(cd, 'valid_exchanges', '')),
        ]
        self._add_section("Trading Information", trading_fields, content_layout)

        # Order Types Section
        order_types = getattr(cd, 'order_types', '')
        if order_types:
            order_fields = [("Supported Order Types", order_types)]
            self._add_section("Order Types", order_fields, content_layout)

        # Time & Hours Section
        time_fields = [
            ("Time Zone", getattr(cd, 'time_zone_id', '')),
            ("Trading Hours", self._format_hours(getattr(cd, 'trading_hours', ''))),
            ("Liquid Hours", self._format_hours(getattr(cd, 'liquid_hours', ''))),
        ]
        self._add_section("Time & Hours", time_fields, content_layout)

        # Additional Info Section (if futures)
        if self.asset.asset_type.value == 'future':
            futures_fields = [
                ("Contract Month", getattr(cd, 'contract_month', '')),
                ("Last Trade Date", getattr(contract, 'last_trade_date', '') if contract else ''),
                ("Real Expiration Date", getattr(cd, 'real_expiration_date', '')),
                ("Multiplier", getattr(contract, 'multiplier', '') if contract else ''),
                ("Underlying Symbol", getattr(cd, 'under_symbol', '')),
            ]
            self._add_section("Futures Details", futures_fields, content_layout)

        # Add stretch at the end
        content_layout.addStretch()

    def _add_section(
        self,
        title: str,
        fields: List[Tuple[str, str]],
        layout: QVBoxLayout
    ) -> None:
        """Add a section with title and fields."""
        # Filter out empty fields
        fields = [(label, value) for label, value in fields if value]

        if not fields:
            return

        # Section header
        header = QLabel(title)
        header.setProperty("class", "section-header")
        header.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #1e293b; "
            "padding: 10px 0 5px 0; border-bottom: 2px solid #e2e8f0;"
        )
        layout.addWidget(header)

        # Section frame
        frame = QFrame()
        frame.setProperty("class", "info-section")
        frame.setStyleSheet(
            "QFrame { background-color: #ffffff; border: 1px solid #e2e8f0; "
            "border-radius: 8px; padding: 15px; }"
        )

        grid = QGridLayout(frame)
        grid.setSpacing(10)
        grid.setContentsMargins(15, 15, 15, 15)

        for row, (label_text, value_text) in enumerate(fields):
            # Label
            label = QLabel(label_text)
            label.setProperty("class", "field-label")
            label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 500;")

            # Value
            value = QLabel(str(value_text))
            value.setProperty("class", "field-value")
            value.setStyleSheet("font-size: 14px; color: #1e293b;")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)

        # Set column stretch
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 3)

        layout.addWidget(frame)

    def _format_hours(self, hours_str: str) -> str:
        """Format trading hours string to be more readable."""
        if not hours_str:
            return ""

        # Split by semicolons and format each segment
        segments = hours_str.split(";")
        formatted = []

        for segment in segments[:3]:  # Show first 3 segments
            if segment.strip():
                formatted.append(segment.strip())

        result = "\n".join(formatted)
        if len(segments) > 3:
            result += f"\n... and {len(segments) - 3} more"

        return result

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("InfoPage destroying...")

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("InfoPage deleted")
