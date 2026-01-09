"""
Calendar Page - displays upcoming calendar events from IB Wall Street Horizon.

Shows earnings dates, dividends, splits and other corporate events.
Falls back to external links if IB data is not available.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.application.bootstrap import get_app
from src.domain.entities.asset import Asset
from src.presentation.core.base_view import BaseView

log = logging.getLogger("CellarLogger")


class CalendarPage(BaseView):
    """
    Page for displaying calendar events.

    Tries to fetch events from IB Wall Street Horizon API first.
    Falls back to external links if data is not available.
    """

    ui_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "calendar_page.ui"
    )
    qss_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "calendar_page.qss"
    )

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("CalendarPage initializing...")

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]
        self.symbol = self.asset.symbol.upper()

        # Store events data
        self.events: List[Dict[str, Any]] = []
        self.wsh_error: Optional[str] = None

        # Show loading state
        self._show_loading()

        # Try to fetch WSH data
        try:
            self._fetch_wsh_events()
        except Exception as e:
            log.error(f"Error fetching WSH events: {e}")
            self.wsh_error = str(e)
            self._build_display()

    def _show_loading(self) -> None:
        """Show loading state."""
        content_layout = self.contentLayout

        # Clear existing content
        while content_layout.count():
            item = content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Header
        header = QLabel(f"Calendar Events for {self.symbol}")
        header.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #1e293b; padding-bottom: 10px;"
        )
        content_layout.addWidget(header)

        # Loading message
        loading = QLabel("Loading calendar events from Interactive Brokers...")
        loading.setObjectName("loadingLabel")
        loading.setStyleSheet("font-size: 14px; color: #64748b; padding: 20px;")
        content_layout.addWidget(loading)

        content_layout.addStretch()

    def _fetch_wsh_events(self) -> None:
        """Fetch WSH events from IB."""
        app = get_app()

        # Check if IB is connected
        if not app.broker_client or not app.broker_client.is_connected():
            log.warning("IB not connected, showing external links")
            self.wsh_error = "IB not connected"
            self._build_display()
            return

        # Get contract ID from asset
        con_id = None
        if self.asset.contract_details:
            cd = self.asset.contract_details[0]
            if hasattr(cd, 'contract') and cd.contract:
                con_id = cd.contract.con_id
            elif hasattr(cd, 'con_id'):
                con_id = cd.con_id

        if not con_id:
            log.warning(f"No contract ID for {self.symbol}, showing external links")
            self.wsh_error = "No contract ID available"
            self._build_display()
            return

        # Calculate date range (today to 90 days from now)
        today = datetime.now()
        start_date = today.strftime("%Y%m%d")
        end_date = (today + timedelta(days=90)).strftime("%Y%m%d")

        log.info(f"Requesting WSH events for con_id={con_id}, {start_date} to {end_date}")

        # Request WSH events
        app.broker_client.get_wsh_event_data(
            con_id=con_id,
            start_date=start_date,
            end_date=end_date,
            limit=50,
            callback=self._on_wsh_data_received,
        )

    def _on_wsh_data_received(self, data_json: str) -> None:
        """Handle WSH event data response."""
        log.info(f"WSH data received: {len(data_json) if data_json else 0} chars")

        if not data_json:
            self.wsh_error = "No data received"
            self._build_display()
            return

        try:
            data = json.loads(data_json)
            log.info(f"WSH data parsed: {data}")

            # Extract events from response
            if isinstance(data, dict):
                # Check for events array
                if "events" in data:
                    self.events = data["events"]
                elif "wshEventData" in data:
                    self.events = data["wshEventData"]
                else:
                    # Maybe the data itself is the events
                    self.events = [data] if data else []
            elif isinstance(data, list):
                self.events = data
            else:
                self.events = []

            log.info(f"Parsed {len(self.events)} events")

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse WSH JSON: {e}")
            self.wsh_error = f"Failed to parse data: {e}"
            self.events = []

        self._build_display()

    def _build_display(self) -> None:
        """Build the display with events or fallback links."""
        content_layout = self.contentLayout

        # Clear existing content
        while content_layout.count():
            item = content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Header
        header = QLabel(f"Calendar Events for {self.symbol}")
        header.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #1e293b; padding-bottom: 10px;"
        )
        content_layout.addWidget(header)

        # Show events if available
        if self.events:
            self._build_events_display(content_layout)
        else:
            # Show error message if any
            if self.wsh_error:
                error_label = QLabel(f"Could not load IB calendar data: {self.wsh_error}")
                error_label.setStyleSheet("font-size: 12px; color: #f97316; padding-bottom: 10px;")
                content_layout.addWidget(error_label)

            # Show message when no events available
            desc = QLabel(
                "No calendar events available. Wall Street Horizon data requires an IB subscription."
            )
            desc.setStyleSheet("font-size: 13px; color: #64748b; padding-bottom: 20px;")
            desc.setWordWrap(True)
            content_layout.addWidget(desc)

        content_layout.addStretch()

    def _build_events_display(self, layout: QVBoxLayout) -> None:
        """Build display for WSH events."""
        desc = QLabel("Upcoming events from Wall Street Horizon:")
        desc.setStyleSheet("font-size: 13px; color: #64748b; padding-bottom: 15px;")
        layout.addWidget(desc)

        # Group events by type
        event_groups: Dict[str, List[Dict]] = {}
        for event in self.events:
            event_type = event.get("eventType", event.get("type", "Other"))
            if event_type not in event_groups:
                event_groups[event_type] = []
            event_groups[event_type].append(event)

        # Color map for event types
        type_colors = {
            "Earnings": "#6366f1",  # Indigo
            "Dividend": "#22c55e",  # Green
            "Split": "#f97316",     # Orange
            "Conference": "#0ea5e9", # Sky blue
            "Other": "#64748b",     # Gray
        }

        for event_type, events in event_groups.items():
            color = type_colors.get(event_type, "#64748b")
            self._add_event_section(event_type, events, layout, color)

    def _add_event_section(
        self,
        event_type: str,
        events: List[Dict],
        layout: QVBoxLayout,
        accent_color: str,
    ) -> None:
        """Add a section for a specific event type."""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 12px;
                margin: 6px 0;
            }}
        """)

        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 10, 12, 10)
        frame_layout.setSpacing(8)

        # Section header
        header = QLabel(f"{event_type} ({len(events)})")
        header.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {accent_color};")
        frame_layout.addWidget(header)

        # Event list
        for event in events[:5]:  # Show max 5 events per type
            event_widget = self._create_event_widget(event)
            frame_layout.addWidget(event_widget)

        if len(events) > 5:
            more_label = QLabel(f"... and {len(events) - 5} more")
            more_label.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic;")
            frame_layout.addWidget(more_label)

        layout.addWidget(frame)

    def _create_event_widget(self, event: Dict) -> QWidget:
        """Create a widget for a single event."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        # Date
        date_str = event.get("date", event.get("eventDate", ""))
        if date_str:
            try:
                # Try to parse and format the date
                if len(date_str) == 8:  # YYYYMMDD
                    dt = datetime.strptime(date_str, "%Y%m%d")
                    date_display = dt.strftime("%b %d, %Y")
                else:
                    date_display = date_str
            except ValueError:
                date_display = date_str
        else:
            date_display = "TBD"

        date_label = QLabel(date_display)
        date_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1e293b; min-width: 100px;")
        layout.addWidget(date_label)

        # Description
        desc = event.get("description", event.get("eventName", event.get("title", "")))
        if not desc:
            desc = event.get("eventType", "Event")
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("font-size: 12px; color: #475569;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 1)

        return widget

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("CalendarPage destroying...")

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("CalendarPage deleted")
