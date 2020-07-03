import logging
from typing import Any

from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot

from ui.base.base_page import BasePage

# create logger
log = logging.getLogger("CellarLogger")


class BasicInfoPage(BasePage):
    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("Running ...")

        # load template
        uic.loadUi(
            "ui/windows/asset_detail/shared/pages/basic_info/basic_info.ui",
            self,
        )

        # load styles
        with open(
            "ui/windows/asset_detail/shared/pages/basic_info/basic_info.qss",
            "r",
        ) as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WA_StyledBackground, True)

        # INPUT data
        self.asset = kwargs["data"]
        self.mainContractDetail = self.asset.contractDetails[0]

        self.fillBasicInfo()

    def fillBasicInfo(self):
        self.localSymbolLabel.setText(
            self.mainContractDetail.contract.localSymbol
        )
        self.longNameLabel.setText(self.mainContractDetail.longName)

        self.industryLabel.setText(self.mainContractDetail.industry)
        self.categoryLabel.setText(self.mainContractDetail.category)
        self.subcategoryLabel.setText(self.mainContractDetail.subcategory)

        self.minTicksLabel.setText(f"{self.mainContractDetail.minTick}")
        self.multiplierLabel.setText(
            f"{self.mainContractDetail.mdSizeMultiplier}"
        )

        self.primaryExchangeLabel.setText(
            self.mainContractDetail.contract.primaryExchange
        )
        self.exchangeLabel.setText(self.mainContractDetail.contract.exchange)

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
