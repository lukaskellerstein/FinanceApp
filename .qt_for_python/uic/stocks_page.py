# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/home/lukas/Projects/Github/lukaskellerstein/FinanceApp/finance_app/ui/windows/main/pages/watchlists/stocks/stocks_page.ui'
#
# Created by: PyQt5 UI code generator 5.14.0
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(504, 290)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Form.sizePolicy().hasHeightForWidth())
        Form.setSizePolicy(sizePolicy)
        self.gridLayout = QtWidgets.QGridLayout(Form)
        self.gridLayout.setObjectName("gridLayout")
        self.loadSavedLayoutButton = QtWidgets.QPushButton(Form)
        self.loadSavedLayoutButton.setStyleSheet("")
        self.loadSavedLayoutButton.setObjectName("loadSavedLayoutButton")
        self.gridLayout.addWidget(self.loadSavedLayoutButton, 0, 2, 1, 1)
        self.ticker1Input = QtWidgets.QLineEdit(Form)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.ticker1Input.sizePolicy().hasHeightForWidth())
        self.ticker1Input.setSizePolicy(sizePolicy)
        self.ticker1Input.setObjectName("ticker1Input")
        self.gridLayout.addWidget(self.ticker1Input, 0, 0, 1, 1)
        self.startRealtime1Button = QtWidgets.QPushButton(Form)
        self.startRealtime1Button.setObjectName("startRealtime1Button")
        self.gridLayout.addWidget(self.startRealtime1Button, 0, 1, 1, 1)
        self.logButton = QtWidgets.QPushButton(Form)
        self.logButton.setObjectName("logButton")
        self.gridLayout.addWidget(self.logButton, 0, 3, 1, 1)
        self.tableBox1 = QtWidgets.QVBoxLayout()
        self.tableBox1.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.tableBox1.setObjectName("tableBox1")
        self.gridLayout.addLayout(self.tableBox1, 1, 0, 1, 4)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.loadSavedLayoutButton.setText(_translate("Form", "Load saved order"))
        self.loadSavedLayoutButton.setProperty("class", _translate("Form", "redbutton"))
        self.ticker1Input.setText(_translate("Form", "AAPL"))
        self.startRealtime1Button.setText(_translate("Form", "Add"))
        self.logButton.setText(_translate("Form", "Log"))
