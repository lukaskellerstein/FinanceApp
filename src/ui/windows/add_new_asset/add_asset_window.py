from src.business.model.factory.asset_factory import AssetFactory
from src.business.model.factory.contract_factory import ContractFactory, SecType
from src.business.model.contracts import IBContract
import logging
from typing import Any, List, Union

from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QHeaderView, QLabel, QWidget
from rx import operators as ops

from src.business.model.asset import Asset, AssetType
from src.business.model.contract_details import IBContractDetails
from src.business.modules.asset_bl import AssetBL
from src.ui.components.contract_details_table.table_model_factory import (
    ContractDetailsTableModelFactory,
)

from src.ui.components.contract_details_table.table import (
    AssetContractDetailsTable,
)
from PyQt6.QtWidgets import QApplication
from src.business.modules.asset_bl import AssetBL

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

        uic.loadUi("src/ui/windows/add_new_asset/add_asset_window.ui", self)

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

        # Business object factory
        self.contractFactory = ContractFactory()
        self.assetFactory = AssetFactory()

    @pyqtSlot()
    def checkSymbolAtBroker(self) -> None:
        symbol: str = self.symbolInput.text().upper()
        exchange: str = self.exchangeInput.text()
        self.asset = self.assetFactory.createNewAsset(self.assetType, symbol)

        log.info(f"symbol={symbol}, exchange={exchange}")

        contract: IBContract
        secType: SecType = SecType.from_str(self.assetType.value)
        if exchange != "":
            contract = self.contractFactory.createNewIBContract(
                secType, symbol, exchange=exchange
            )
        else:
            contract = self.contractFactory.createNewIBContract(
                secType, symbol
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
        screen = QApplication.primaryScreen()
        screenGeometry = screen.geometry()
        x = (screenGeometry.width() - self.width()) / 2
        y = (screenGeometry.height() - self.height()) / 2
        self.move(int(x), int(y))

    # region "checkSymbolAtBroker" operators

    @pyqtSlot(list)
    def __fillTable(self, data: List[Union[IBContractDetails, List]]):
        self.clearTableBox()

        # Check for empty data, list (error format), or dict (error from IB API)
        if len(data) == 0 or type(data[0]) is list or type(data[0]) is dict:
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
        # Only add valid IBContractDetails, skip error dicts
        for item in data:
            if not isinstance(item, dict):
                self.asset.contractDetails.append(item)

    # endregion

    @pyqtSlot()
    def saveToDb(self):
        # Validate that we have contract details before saving
        if not self.asset.contractDetails or len(self.asset.contractDetails) == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Cannot Save",
                "No valid contract details found. Please search for a valid symbol first."
            )
            return

        note: str = self.noteInput.text()
        self.asset.shortDescription = note

        if self.bl.isExist(self.assetType, self.asset.symbol) == False:
            self.bl.save(self.asset)

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
