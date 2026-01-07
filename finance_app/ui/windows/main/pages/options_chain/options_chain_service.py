"""
Service layer for Options Chain page.
Integrates business logic with state management.
"""
import logging
from typing import Any, Dict, List, Optional

from rx import merge, of
from rx import operators as ops
from rx.core.typing import Observable
from rx.subject import BehaviorSubject

from finance_app.business.modules.options_chain_bl import OptionsChainBL
from finance_app.business.model.contracts import IBOptionContract, IBStockContract
from finance_app.ui.state.main import State
from finance_app.ui.services.realtime_data_service import RealtimeDataService
from finance_app.business.model.asset import AssetType

# create logger
log = logging.getLogger("CellarLogger")


class OptionsChainService(object):
    """Service integrates BL and State management for Options Chain"""

    def __init__(self):
        log.info("Running ...")

        # State
        self.state = State.getInstance()

        # BL
        self.bl = OptionsChainBL()

        # Realtime data service for underlying
        self.realtimeService = RealtimeDataService()

        # Track active subscriptions
        self.subscriptions = []

    def getOptionChain(self, symbol: str) -> Observable:
        """
        Get option chain (expirations and strikes) for a symbol.
        Returns Observable emitting dict with 'exchange', 'expirations', 'strikes'.
        """
        return self.bl.getOptionChainForSymbol(symbol).pipe(
            ops.do_action(lambda x: log.info(f"Option chain received: {len(x.get('expirations', []))} expirations, {len(x.get('strikes', []))} strikes")),
        )

    def startUnderlyingRealtime(self, symbol: str) -> Dict[str, Any]:
        """
        Start realtime data for the underlying stock.
        Returns dict with RealtimeDataItem.
        """
        return self.realtimeService.startRealtime(AssetType.STOCK, symbol)

    def startOptionsRealtime(
        self,
        symbol: str,
        expiration: str,
        strikes: List[float],
        exchange: str = "SMART",
    ) -> Dict[str, Observable]:
        """
        Start realtime data for options at given strikes.
        Returns dict mapping strike to Observable of tick data.
        """
        log.info(f"startOptionsRealtime - symbol: {symbol}, expiration: {expiration}, strikes: {len(strikes)}, exchange: {exchange}")
        result = {}

        for strike in strikes:
            # Create call contract
            call_contract = self.bl.createOptionContract(
                symbol=symbol,
                expiration=expiration,
                strike=strike,
                right="C",
                exchange=exchange,
            )
            log.debug(f"Starting realtime for CALL: {symbol} {expiration} {strike}")
            call_obs = self.bl.startRealtimeOptions(call_contract)
            result[f"{strike}_C"] = call_obs

            # Create put contract
            put_contract = self.bl.createOptionContract(
                symbol=symbol,
                expiration=expiration,
                strike=strike,
                right="P",
                exchange=exchange,
            )
            log.debug(f"Starting realtime for PUT: {symbol} {expiration} {strike}")
            put_obs = self.bl.startRealtimeOptions(put_contract)
            result[f"{strike}_P"] = put_obs

        log.info(f"Created {len(result)} option subscriptions")
        return result

    def getFilteredStrikes(
        self,
        all_strikes: List[float],
        spot_price: float,
        num_strikes: int = 11,
    ) -> List[float]:
        """
        Filter strikes to show only strikes around the spot price.
        Returns list of strikes centered around ATM.
        """
        if not all_strikes or spot_price <= 0:
            return []

        sorted_strikes = sorted(all_strikes)

        # Find ATM strike (closest to spot price)
        atm_idx = min(
            range(len(sorted_strikes)),
            key=lambda i: abs(sorted_strikes[i] - spot_price)
        )

        # Calculate range around ATM
        half = num_strikes // 2
        start_idx = max(0, atm_idx - half)
        end_idx = min(len(sorted_strikes), start_idx + num_strikes)

        # Adjust start if we hit the end
        if end_idx - start_idx < num_strikes:
            start_idx = max(0, end_idx - num_strikes)

        return sorted_strikes[start_idx:end_idx]

    def getFilteredExpirations(
        self,
        all_expirations: List[str],
        num_expirations: int = 12,
    ) -> List[str]:
        """
        Filter expirations to show only the nearest ones.
        Returns list of nearest expiration dates.
        """
        if not all_expirations:
            return []

        sorted_expirations = sorted(all_expirations)
        return sorted_expirations[:num_expirations]

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self):
        log.info("Destroying ...")

        # Unsubscribe everything
        for sub in self.subscriptions:
            try:
                sub.dispose()
            except Exception as e:
                log.error(f"Error disposing subscription: {e}")

        # Destroy BL
        self.bl.onDestroy()

    def __del__(self):
        log.info("Running ...")
