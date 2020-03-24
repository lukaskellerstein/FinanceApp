import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ib_insync.contract import Stock, Contract

# UI
from ui.core.pages.base_page import BasePage
from ui.state.main import State

# BUSINESS
from business.services.ib_data_service import IBDataService
from business.core.task_manager import TaskManager
from business.modules.futures_watchlist import FuturesWatchlistBL

from helpers import printObject


class FuturesPage(BasePage):
    def __init__(self):
        BasePage.__init__(
            self, "ui/pages/overview/futures/main.glade", "FuturesMainGrid"
        )

        self.bl = FuturesWatchlistBL()

        # self.ls = Gtk.ListStore(str, float, float, float, float, float, float, float)

        # create a TreeStore with one string column to use as the model
        self.ts = Gtk.TreeStore(str, float, float, float, float, float, float, float)

        # # add row
        # row1 = store.append(None, ["CL", 0, 0, 0, 0])
        # store.append(row1, ["CLZ0", 100, 105, 95, 110])
        # store.append(row1, ["CLZ1", 100, 105, 95, 110])
        # store.append(row1, ["CLZ2", 100, 105, 95, 110])
        # store.append(row1, ["CLZ3", 100, 105, 95, 110])
        # store.append(row1, ["CLZ4", 100, 105, 95, 110])

        # # add another row
        # row2 = store.append(None, ["ES", 0, 0, 0, 0])
        # store.append(row2, ["ESZ0", 100, 105, 95, 110])
        # store.append(row2, ["ESZ1", 100, 105, 95, 110])
        # store.append(row2, ["ESZ2", 100, 105, 95, 110])
        # store.append(row2, ["ESZ3", 100, 105, 95, 110])
        # store.append(row2, ["ESZ4", 100, 105, 95, 110])


        self.tw = Gtk.TreeView(self.ts)
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

        self.add_btn = self.builder.get_object("AddButton")
        self.add_btn.connect("clicked", self.add_button_click)
        self.add_input = self.builder.get_object("AddInput")

        self.bl.state.futures_realtime_data.data.subscribe(
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
        ticker = self.add_input.get_text().upper()
        self.bl.add(ticker)

    def set_table_data(self, data):
        print(data)
        # self.ls.clear()
        # for row in data.itertuples(index=True):
        #     self.ls.append(
        #         [
        #             str(row.Index),
        #             row.bidSize,
        #             row.bid,
        #             row.ask,
        #             row.askSize,
        #             row.high,
        #             row.low,
        #             row.close,
        #         ]
        #     )
