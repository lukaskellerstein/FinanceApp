from db.model.base import DBObject
import logging
import threading
from typing import Any, Callable, Dict, List

from business.model.contracts import (
    IBContract,
    IBFutureContract,
    IBStockContract,
)
from db.services.model import LlContractDetails
from ibapi.contract import Contract, ContractDetails
from datetime import datetime
import pandas as pd

# create logger
log = logging.getLogger("CellarLogger")


from math import ceil


def week_of_month(dt):
    """ Returns the week of the month for the specified date.
    """

    count = 0
    if dt.day <= 7:
        count = 1
    elif dt.day > 7 and dt.day <= 14:
        count = 2
    elif dt.day > 14 and dt.day <= 21:
        count = 3
    elif dt.day > 21 and dt.day <= 28:
        count = 4
    elif dt.day > 28:
        count = 5

    return count

    # res = (dt.day + dt.weekday()) / 7 + 1

    # first_day = dt.replace(day=1)

    # dom = dt.day
    # adjusted_dom = dom + first_day.weekday()

    # # return int(ceil(adjusted_dom / 7.0))
    # print(f"{res} --> {ceil(res)}")
    # return ceil(res)


def try_parsing_date(text, formats: List[str]) -> datetime:
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError("no valid date format found")


def logThreads():
    log.info(f"Threads count: {threading.active_count()}")
    log.info("Thread names:")
    for thread in threading.enumerate():
        log.info(f"- {thread.getName()}")


def getColorByYieldValue(value: int):
    if value <= -25:
        return "#b71c1c"
    elif value > -25 and value <= -10:
        return "#d32f2f"
    elif value > -10 and value <= -6:
        return "#f44336"
    elif value > -6 and value <= -3:
        return "#e57373"
    elif value > -3 and value < 0:
        return "#ffcdd2"
    elif value == 0:
        return "white"
    elif value > 0 and value < 3:
        return "#c8e6c9"
    elif value >= 3 and value < 6:
        return "#81c784"
    elif value >= 6 and value < 10:
        return "#4caf50"
    elif value >= 10 and value < 25:
        return "#388e3c"
    elif value >= 25:
        return "#1b5e20"


def getStock(ticker: str):
    contract = Contract()
    contract.symbol = ticker
    contract.secType = "STK"
    contract.exchange = "SMART"
    contract.currency = "USD"
    contract.primaryExchange = "NASDAQ"
    return contract


def pd_insert_row(
    idx: int, df: pd.DataFrame, df_insert: pd.DataFrame
) -> pd.DataFrame:
    log.debug(f"INSERT ROW - {idx}")
    # print(df_insert)
    # print(type(df_insert))

    idx += 1
    dfA = df.iloc[
        :idx,
    ]
    dfB = df.iloc[
        idx:,
    ]

    print(idx)

    print("----dfA----")
    print(dfA)
    print("----dfB----")
    print(dfB)

    idx_name = df_insert.name
    print("-------Name---------")
    print(idx_name)
    print("--------------------")

    if idx_name in dfA.index:
        dfA = dfA.drop(idx_name, axis=0)

    if idx_name in dfB.index:
        dfB = dfB.drop(idx_name, axis=0)

    print("----dfA----")
    print(dfA)
    print("----dfB----")
    print(dfB)

    df2 = dfA.append(df_insert, ignore_index=False).append(dfB)
    print("-------DF2---------")
    print(df2)
    print("--------------------")

    # # aaa = pd.concat([dfA, df_insert, dfB])
    # # print(aaa)

    # # df2 = dfA.append(df_insert).append(dfB).reset_index(drop=True)

    return df2


def obj_to_dict(obj: Any) -> Any:
    if type(obj) is dict:
        res = {}
        for k, v in obj.items():
            res[k] = obj_to_dict(v)
        return res
    elif type(obj) is list:
        return [obj_to_dict(item) for item in obj]
    elif type(obj) is LlContractDetails:
        return obj_to_dict(vars(obj))
    else:
        return obj


def mapDictToLlContractDetail(d: Dict[str, Any]) -> LlContractDetails:

    secType = d["secType"]

    # contract -------------
    resultContract: IBContract

    if secType == "STK":
        resultContract = IBStockContract(symbol="", localSymbol="")
    elif secType == "FUT":
        resultContract = IBFutureContract(symbol="", localSymbol="")
    else:
        resultContract = IBContract(symbol="", localSymbol="")

    if resultContract is not None:
        resultContract.conId = d["conId"]
        resultContract.symbol = d["symbol"]
        resultContract.secType = d["secType"]
        resultContract.lastTradeDateOrContractMonth = d[
            "lastTradeDateOrContractMonth"
        ]
        resultContract.strike = d["strike"]
        resultContract.right = d["right"]
        resultContract.multiplier = d["multiplier"]
        resultContract.exchange = d["exchange"]
        resultContract.primaryExchange = d["primaryExchange"]
        resultContract.currency = d["currency"]
        resultContract.localSymbol = d["localSymbol"]
        resultContract.tradingClass = d["tradingClass"]
        resultContract.includeExpired = d["includeExpired"]
        resultContract.secIdType = d["secIdType"]
        resultContract.secId = d["secId"]
        resultContract.comboLegsDescrip = d["comboLegsDescrip"]
        resultContract.comboLegs = d["comboLegs"]
        resultContract.deltaNeutralContract = (
            d["deltaNeutralContract"] if "deltaNeutralContract" in d else ""
        )
    # ---------------------

    result = LlContractDetails(resultContract)

    result.marketName = d["marketName"]
    result.minTick = d["minTick"]
    result.orderTypes = d["orderTypes"]
    result.validExchanges = d["validExchanges"]
    result.priceMagnifier = d["priceMagnifier"]
    result.underConId = d["underConId"]
    result.longName = d["longName"]
    result.contractMonth = d["contractMonth"]
    result.industry = d["industry"]
    result.category = d["category"]
    result.subcategory = d["subcategory"]
    result.timeZoneId = d["timeZoneId"]
    result.tradingHours = d["tradingHours"]
    result.liquidHours = d["liquidHours"]
    result.evRule = d["evRule"]
    result.evMultiplier = d["evMultiplier"]
    result.mdSizeMultiplier = d["mdSizeMultiplier"]
    result.aggGroup = d["aggGroup"]
    result.underSymbol = d["underSymbol"]
    result.underSecType = d["underSecType"]
    result.marketRuleIds = d["marketRuleIds"]
    # result.secIdList = d["secIdList"]
    result.realExpirationDate = d["realExpirationDate"]
    result.lastTradeTime = d["lastTradeTime"]
    # BOND values
    result.cusip = d["cusip"]
    result.ratings = d["ratings"]
    result.descAppend = d["descAppend"]
    result.bondType = d["bondType"]
    result.couponType = d["couponType"]
    result.callable = d["callable"]
    result.putable = d["putable"]
    result.coupon = d["coupon"]
    result.convertible = d["convertible"]
    result.maturity = d["maturity"]
    result.issueDate = d["issueDate"]
    result.nextOptionDate = d["nextOptionDate"]
    result.nextOptionType = d["nextOptionType"]
    result.nextOptionPartial = d["nextOptionPartial"]
    result.notes = d["notes"]
    # ---------------------

    return result


def mapContractDetailsToLl(cd: ContractDetails) -> LlContractDetails:
    # contract -------------
    result = LlContractDetails(IBContract(**cd.contract))
    # result.conId = cd.contract.conId
    # result.symbol = cd.contract.symbol
    # result.secType = cd.contract.secType
    # result.lastTradeDateOrContractMonth = cd.contract.lastTradeDateOrContractMonth
    # result.strike = cd.contract.strike
    # result.right = cd.contract.right
    # result.multiplier = cd.contract.multiplier
    # result.exchange = cd.contract.exchange
    # result.primaryExchange = cd.contract.primaryExchange
    # result.currency = cd.contract.currency
    # result.localSymbol = cd.contract.localSymbol
    # result.tradingClass = cd.contract.tradingClass
    # result.includeExpired = cd.contract.includeExpired
    # result.secIdType = cd.contract.secIdType
    # result.secId = cd.contract.secId
    # result.comboLegsDescrip = cd.contract.comboLegsDescrip
    # result.comboLegs = cd.contract.comboLegs
    # result.deltaNeutralContract = cd.contract.deltaNeutralContract
    # ---------------------
    result.marketName = cd.marketName
    result.minTick = cd.minTick
    result.orderTypes = cd.orderTypes
    result.validExchanges = cd.validExchanges
    result.priceMagnifier = cd.priceMagnifier
    result.underConId = cd.underConId
    result.longName = cd.longName
    result.contractMonth = cd.contractMonth
    result.industry = cd.industry
    result.category = cd.category
    result.subcategory = cd.subcategory
    result.timeZoneId = cd.timeZoneId
    result.tradingHours = cd.tradingHours
    result.liquidHours = cd.liquidHours
    result.evRule = cd.evRule
    result.evMultiplier = cd.evMultiplier
    result.mdSizeMultiplier = cd.mdSizeMultiplier
    result.aggGroup = cd.aggGroup
    result.underSymbol = cd.underSymbol
    result.underSecType = cd.underSecType
    result.marketRuleIds = cd.marketRuleIds
    # result.secIdList = cd.secIdList
    result.realExpirationDate = cd.realExpirationDate
    result.lastTradeTime = cd.lastTradeTime
    # BOND values
    result.cusip = cd.cusip
    result.ratings = cd.ratings
    result.descAppend = cd.descAppend
    result.bondType = cd.bondType
    result.couponType = cd.couponType
    result.callable = cd.callable
    result.putable = cd.putable
    result.coupon = cd.coupon
    result.convertible = cd.convertible
    result.maturity = cd.maturity
    result.issueDate = cd.issueDate
    result.nextOptionDate = cd.nextOptionDate
    result.nextOptionType = cd.nextOptionType
    result.nextOptionPartial = cd.nextOptionPartial
    result.notes = cd.notes

    return result


def mapLlContractDetailsToContract(cd: LlContractDetails) -> Any:
    if cd is not None:

        result = None

        if cd.secType == "STK":
            result = IBStockContract(
                symbol=cd.symbol, localSymbol=cd.localSymbol
            )
        elif cd.secType == "FUT":
            result = IBFutureContract(
                symbol=cd.symbol, localSymbol=cd.localSymbol
            )

        if result is not None:
            result.conId = cd.conId
            result.lastTradeDateOrContractMonth = (
                cd.lastTradeDateOrContractMonth
            )
            result.strike = cd.strike
            result.right = cd.right
            result.multiplier = cd.multiplier
            result.exchange = cd.exchange
            result.primaryExchange = cd.primaryExchange
            result.currency = cd.currency
            result.tradingClass = cd.tradingClass
            result.includeExpired = cd.includeExpired
            result.secIdType = cd.secIdType
            result.secId = cd.secId

            result.comboLegs = cd.comboLegs
            result.comboLegsDescrip = cd.comboLegsDescrip

            result.deltaNeutralContract = cd.deltaNeutralContract

        return result
    else:
        raise Exception("cd should not be empty")
