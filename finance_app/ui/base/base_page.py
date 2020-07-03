import logging
from typing import Any, Dict, Tuple

from PyQt5.QtWidgets import QWidget

# create logger
log = logging.getLogger("CellarLogger")


class BasePage(QWidget):
    def __init__(self, *args: Tuple[str, Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        log.info("Running ...")

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
