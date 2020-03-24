import pandas as pd

from rx import operators as ops
from rx.subject import BehaviorSubject

from ui.state.stocks_realtime_data import StocksRealtimeDataState
from ui.state.stocks_watchlist import StocksWatchlistState
from ui.state.futures_realtime_data import FuturesRealtimeDataState
from ui.state.futures_watchlist import FuturesWatchlistState


class State:

    __instance = None

    stocks_realtime_data = StocksRealtimeDataState()
    futures_realtime_data = FuturesRealtimeDataState()
    stocks_watchlist = StocksWatchlistState()
    futures_watchlist = FuturesWatchlistState()

    @staticmethod
    def getInstance():
        """ Static access method. """
        if State.__instance == None:
            State()
        return State.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if State.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            State.__instance = self
