from PyQt5.QtCore import pyqtSignal, QModelIndex
from PyQt5.QtWidgets import QTreeView, QHeaderView

from ui.windows.main.pages.watchlists.futures.table.item_delegate import (
    MyRenderDelegate,
)
from ui.windows.main.pages.watchlists.futures.table.tree_model import (
    FuturesTreeModel,
)


class FuturesTree(QTreeView):

    on_remove = pyqtSignal(object, name="on_remove")

    def __init__(self):
        super(QTreeView, self).__init__()

        # load styles
        with open("ui/pages/watchlists/futures/table/tree.qss", "r") as fh:
            self.setStyleSheet(fh.read())

        self.tree_header_data = [
            "symbol",
            "localSymbol",
            "contractMonth",
            "contractEndDate",
            "diff",
            "bid_size",
            "bid",
            "last",
            "ask",
            "ask_size",
            "open",
            "high",
            "low",
            "close",
            "change",
            "volume",
            "avg_volume",
            "option_historical_vol",
            "option_implied_vol",
            "delete",
        ]
        self.tree_model = FuturesTreeModel([], self.tree_header_data)
        self.setModel(self.tree_model)

        header = self.header()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        # header.setSectionResizeMode(5, QHeaderView.Stretch)

        self.setItemDelegate(MyRenderDelegate(self))

        self.clicked.connect(self.myclick)

    def myclick(self, index: QModelIndex):
        if index.column() == 19:
            row = self.tree_model.root.child(index.row())
            self.on_remove.emit(row)
