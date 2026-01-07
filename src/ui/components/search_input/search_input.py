from PyQt6 import uic
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPaintEvent


class SearchInput(QWidget):
    text: str = ""

    # Output event
    on_textChanged = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        # load template
        uic.loadUi("src/ui/components/search_input/search_input.ui", self)

        # load styles
        with open("src/ui/components/search_input/search_input.qss", "r") as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.input.textChanged.connect(self.textChanged)
        self.input.editingFinished.connect(self.textChangeFinished)

    @pyqtSlot(str)
    def textChanged(self, text: str):
        self.text = text

    @pyqtSlot()
    def textChangeFinished(self):
        self.on_textChanged.emit(self.text)

    # def paintEvent(self, event: QPaintEvent):
    #     painter = QPainter(self)

    #     # Get current state.
    #     parent = self.parent()

    #     print("paintEvent")
