from finance_app.business.model.contract_details import IBContractDetails
import logging
from typing import Tuple, List

import pandas as pd
from PyQt6.QtWidgets import QHeaderView, QTableView
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
from finance_app.business.model.asset import Asset

# create logger
log = logging.getLogger("CellarLogger")


class CDTable(QTableView):
    def __init__(self, asset: Asset):
        super(QTableView, self).__init__()
        self.setSortingEnabled(True)
        self.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)

        self.tableModel = QStandardItemModel()
        self.setData(asset.contractDetails)

        self.setModel(self.tableModel)

        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)

    def setData(self, data: List[IBContractDetails]):
        self.tableModel.clear()

        if len(data) > 0:

            # add columns
            resultColumns = [
                "symbol",
                "localSymbol",
                "lastTradeDateOrContractMonth",
            ]
            self.tableModel.setHorizontalHeaderLabels(resultColumns)

            # add rows
            for cd in data:
                resultRow = []
                resultRow.append(QStandardItem(str(cd.contract.symbol)))
                resultRow.append(QStandardItem(str(cd.contract.localSymbol)))
                resultRow.append(
                    QStandardItem(
                        str(cd.contract.lastTradeDateOrContractMonth)
                    )
                )

                self.tableModel.appendRow(resultRow)

            self.tableModel.sort(2, Qt.SortOrder.DescendingOrder)

