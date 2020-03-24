import asyncio
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ib_insync.contract import Stock

# UI
from ui.core.pages.base_page import BasePage
from ui.state.main import State

# BUSINESS
from business.services.ib_data_service import IBDataService
from business.core.task_manager import TaskManager
from business.modules.stocks_watchlist import StockWatchlistBL

from helpers import printObject


class StocksPage(BasePage):
    def __init__(self):
        BasePage.__init__(self, "ui/pages/overview/stocks/main.glade", "StocksMainGrid")

        self.bl = StockWatchlistBL()

        self.ls = Gtk.ListStore(str, float, float, float, float, float, float, float)
        self.tw = Gtk.TreeView(self.ls)
        self.tw.set_hexpand(True)
        self.tw.set_vexpand(True)

        # all columns
        for i, col_title in enumerate(
            ["Ticker", "BidSize", "Bid", "AskSize", "Ask", "High", "Low", "Close"]
        ):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(col_title, renderer, text=i)
            column.set_sort_column_id(i)
            self.tw.append_column(column)

        # delete button columns
        action_icon = Gtk.CellRendererPixbuf()
        self.delete_action_icon = Gtk.TreeViewColumn("", action_icon, icon_name=2)
        self.tw.append_column(self.delete_action_icon)
        self.tw.connect("button-press-event", self.on_pressed)

        self.template.attach(self.tw, 0, 1, 2, 2)

        self.add_stock_btn = self.builder.get_object("AddStockButton")
        self.add_stock_btn.connect("clicked", self.add_button_click)
        self.add_stock_input = self.builder.get_object("AddStockInput")

        self.bl.state.stocks_realtime_data.data.subscribe(
            lambda x: (self.set_table_data(x))
        )
        self.bl.updateStateFromDB()

        self.template.show_all()

    # click handler
    def on_pressed(self, trview, event):
        print("on_pressed")
        path, col, x, y = trview.get_path_at_pos(event.x, event.y)

        # delete button
        if col is self.delete_action_icon:
            model, row = trview.get_selection().get_selected()
            ticker = model[path][0]
            self.bl.remove(ticker)

    def add_button_click(self, *args):
        ticker = self.add_stock_input.get_text().upper()
        self.bl.add(ticker)

    def set_table_data(self, data):
        self.ls.clear()
        for row in data.itertuples(index=True):
            self.ls.append(
                [
                    str(row.Index),
                    row.bidSize,
                    row.bid,
                    row.ask,
                    row.askSize,
                    row.high,
                    row.low,
                    row.close,
                ]
            )
