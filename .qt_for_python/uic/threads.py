# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file '/home/lukas/Projects/Github/lukaskellerstein/FinanceApp/finance_app/ui/windows/main/pages/debug/realtime_data/threads.ui'
#
# Created by: PyQt5 UI code generator 5.14.0
#
# WARNING! All changes made in this file will be lost!


from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(756, 545)
        self.verticalLayout = QtWidgets.QVBoxLayout(Form)
        self.verticalLayout.setObjectName("verticalLayout")
        self.logButton = QtWidgets.QPushButton(Form)
        self.logButton.setObjectName("logButton")
        self.verticalLayout.addWidget(self.logButton)
        self.logTextEdit = QtWidgets.QTextEdit(Form)
        self.logTextEdit.setObjectName("logTextEdit")
        self.verticalLayout.addWidget(self.logTextEdit)

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        _translate = QtCore.QCoreApplication.translate
        Form.setWindowTitle(_translate("Form", "Form"))
        self.logButton.setText(_translate("Form", "Log"))
