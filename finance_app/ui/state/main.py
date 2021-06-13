from __future__ import (
    annotations,
)  # allow return same type as class ..... -> State

import pandas as pd
from rx import operators as ops
from rx.subject import BehaviorSubject

from ui.state.futures_realtime_data import FuturesRealtimeDataState
from ui.state.stocks_realtime_data import StocksRealtimeDataState

# ******************************
# SINGLETON
# ******************************
class State(object):

    __instance = None

    @staticmethod
    def getInstance() -> State:
        """ Static access method. """
        if State.__instance is None:
            State.__instance = State()
        return State.__instance

    def __init__(self):
        """ Virtually private constructor. """
        if State.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            State.__instance = self

            self.stocks_realtime_data = StocksRealtimeDataState()
            self.futures_realtime_data = FuturesRealtimeDataState()
