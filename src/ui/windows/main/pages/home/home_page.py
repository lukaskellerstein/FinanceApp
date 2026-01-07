import logging
from typing import Any, Dict, Tuple

from PyQt6 import uic
from PyQt6.QtCore import Qt

from src.ui.base.base_page import BasePage

# create logger
log = logging.getLogger("CellarLogger")


class HomePage(BasePage):
    def __init__(self, *args: Tuple[str, Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        log.info("Running ...")
        self.setObjectName("home_page")

        # load template
        uic.loadUi("src/ui/windows/main/pages/home/home_page.ui", self)

        # load styles
        with open("src/ui/windows/main/pages/home/home_page.qss", "r") as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # load styles
        # with open(
        #     "src/ui/pages/futures_watchlist/futures_watchlist_page.qss", "r"
        # ) as fh:
        #     self.setStyleSheet(fh.read())

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # # 1. CUSTOM destroy -----------------------------------------
    # def onDestroy(self):
    #     log.info("Destroying ...")

    # # 2. Python destroy -----------------------------------------
    # def __del__(self):
    #     log.info("Running ...")
