import asyncio
import random
from enum import Enum
import pandas as pd
from ib_insync import IB, util


util.patchAsyncio()


class TickDataType(Enum):
    LAST = "Last"
    ALL_LAST = "AllLast"
    BID_ASK = "BidAsk"
    MIDPOINT = "MidPoint"


class IBDataService:

    ip = "127.0.0.1"
    port = 4002  # 4001 for real trading

    def __init__(self):
        self.uid = random.randint(1000, 10000)
        print(f"init - UID: {str(self.uid)}")
        self.ib = IB()
        self.connect()

    def connect(self, *args):
        print(f"connectToIB - UID: {str(self.uid)}")

        if self.ib.isConnected() is False:
            print("CONNECTING ...")
            self.ib.connect("127.0.0.1", 4002, clientId=self.uid)
            print("CONNECTED")

    def disconnect(self, *args):
        print(f"connectToIB - UID: {str(self.uid)}")

        if self.ib.isConnected():
            print("DISCONNECTING ...")
            self.ib.disconnect()
            print("DISCONNECTED ...")

    def getContractDetail(self, contract):
        print(f"getContractDetail - UID: {str(self.uid)}")
        data = self.ib.reqContractDetails(contract)

        # print(data)

        if len(data) > 0:
            return data[0]
        else:
            return None

    def getFuturesContractDetail(self, contract):
        print(f"getFuturesContractDetail - UID: {str(self.uid)}")
        data = self.ib.reqContractDetails(contract)
        if len(data) > 0:
            return data
        else:
            return None

    def getHistoricalData(
        self, contract, endDate="", duration="1 Y", barSize="1 day", price="MIDPOINT"
    ):
        print(f"getHistoricalData - UID: {str(self.uid)}")
        data = self.ib.reqHistoricalData(
            contract, endDate, duration, barSize, price, 1, 1, False, []
        )
        return data

    async def startRealtimeData(self, contract, method):
        print(f"startRealtimeData - UID: {str(self.uid)}")

        self.ib.reqMktData(contract, "233", False, False)

        ticker = self.ib.reqTickByTickData(contract, TickDataType.LAST.value)
        ticker.updateEvent += method

        print(f"ENDS - startRealtimeData - UID: {str(self.uid)}")

    def stopRealtimeData(self, contract):
        print(f"stopRealtimeData - UID: {str(self.uid)}")

        self.ib.cancelMktData(contract)
        self.ib.cancelTickByTickData(contract, TickDataType.LAST.value)

        print(f"ENDS - stopRealtimeData - UID: {str(self.uid)}")
