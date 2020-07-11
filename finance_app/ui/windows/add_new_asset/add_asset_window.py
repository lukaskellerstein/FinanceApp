from business.model.contracts import IBContract
import logging
from typing import Any, List, Union

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QHeaderView, QLabel, QWidget
from rx import operators as ops

from business.model.asset import Asset, AssetType
from business.model.contract_details import IBContractDetails
from business.model.contracts import ContractFactory
from business.modules.asset_bl import AssetBL
from ui.components.contract_details_table.table_model_factory import (
    ContractDetailsTableModelFactory,
)

from ui.components.contract_details_table.table import (
    AssetContractDetailsTable,
)
from PyQt5.Qt import QApplication
from business.modules.asset_bl import AssetBL

# create logger
log = logging.getLogger("CellarLogger")


class AssetAddWindow(QWidget):

    on_close = pyqtSignal()
    on_fillTable = pyqtSignal(list)

    asset: Asset
    assetType: AssetType

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("Running ...")

        uic.loadUi("ui/windows/add_new_asset/add_asset_window.ui", self)

        # buttons
        self.checkBrokerButton.clicked.connect(self.checkSymbolAtBroker)
        self.saveButton.clicked.connect(self.saveToDb)

        self.on_fillTable.connect(self.__fillTable)

        self.assetType: AssetType = kwargs["assetType"]
        self.bl = AssetBL()

        # set visibility
        if hasattr(self, "table"):
            self.table.setVisible(False)
        self.noteInput.setVisible(False)
        self.noteLabel.setVisible(False)
        self.saveButton.setVisible(False)

        self.adjustSize()

    @pyqtSlot()
    def checkSymbolAtBroker(self) -> None:
        symbol: str = self.symbolInput.text().upper()
        exchange: str = self.exchangeInput.text()
        self.asset = Asset(symbol=symbol, type=self.assetType.value)

        log.info(f"symbol={symbol}, exchange={exchange}")

        contract: IBContract
        if exchange != "":
            contract = ContractFactory.create(
                self.assetType.value, symbol=symbol, exchange=exchange
            )
        else:
            contract = ContractFactory.create(
                self.assetType.value, symbol=symbol
            )

        self.bl.getContractDetails(self.assetType, contract).pipe(
            # We have to use pyqtSignal, otherwise Qt will complain about threads
            # --> Cannot set parent, new parent is in a different thread
            ops.do_action(lambda x: self.on_fillTable.emit(x)),
        ).subscribe(self.__addToAsset)

        # set width
        self.setFixedWidth(800)
        self.setFixedHeight(800)

        # center
        screenGeometry = QApplication.desktop().screenGeometry()
        x = (screenGeometry.width() - self.width()) / 2
        y = (screenGeometry.height() - self.height()) / 2
        self.move(x, y)

    # region "checkSymbolAtBroker" operators

    @pyqtSlot(list)
    def __fillTable(self, data: List[Union[IBContractDetails, List]]):
        self.clearTableBox()

        if len(data) == 0 or type(data[0]) is list:
            if hasattr(self, "table"):
                self.table.setVisible(False)

            self.tableBox.addWidget(QLabel("NO DATA"))
        else:
            self.table = AssetContractDetailsTable(self.assetType)
            self.table.tableModel.setData(data)
            self.tableBox.addWidget(self.table)

        self.noteInput.setVisible(True)
        self.noteLabel.setVisible(True)
        self.saveButton.setVisible(True)

    def __addToAsset(self, data: List[IBContractDetails]):
        [self.asset.contractDetails.append(item) for item in data]

    # endregion

    @pyqtSlot()
    def saveToDb(self):
        note: str = self.noteInput.text()
        self.asset.shortDescription = note

        if self.bl.existInDb(self.assetType, self.asset.symbol) == False:
            self.bl.saveToDb(self.asset)

        self.on_close.emit()

    def clearTableBox(self):
        for i in reversed(range(self.tableBox.count())):
            self.tableBox.itemAt(i).widget().setParent(None)

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # Qt destroy -----------------------------------------
    def closeEvent(self, event: Any):
        log.info("Running ...")

    # Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
