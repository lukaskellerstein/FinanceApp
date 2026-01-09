"""
Mappers for converting between IB API types and domain types.

Provides bidirectional conversion:
- ibapi.Contract <-> domain.Contract
- ibapi.ContractDetails <-> domain.ContractDetails
- ibapi.BarData -> domain.BarData
- Tick data dict -> domain.TickData
"""

from __future__ import annotations
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime, timezone
import logging

from ibapi.contract import Contract as IBApiContract
from ibapi.contract import ContractDetails as IBApiContractDetails

from src.domain.entities.contract import (
    Contract,
    StockContract,
    FutureContract,
    OptionContract,
)
from src.domain.entities.contract_details import ContractDetails
from src.domain.value_objects.bar_data import BarData
from src.domain.value_objects.tick_data import TickData

log = logging.getLogger("CellarLogger")


class IBMapper:
    """
    Mapper for converting between IB API types and domain types.

    This class provides bidirectional conversion between the external
    ibapi library types and our internal domain types, keeping the
    domain layer independent of external dependencies.

    Example:
        mapper = IBMapper()

        # Convert domain to IB
        ib_contract = mapper.to_ib_contract(domain_contract)

        # Convert IB to domain
        domain_contract = mapper.from_ib_contract(ib_contract)
    """

    # Mapping from IB tick type strings to our field names
    TICK_TYPE_MAPPING = {
        "BID": "bid",
        "ASK": "ask",
        "LAST": "last",
        "BID_SIZE": "bid_size",
        "ASK_SIZE": "ask_size",
        "LAST_SIZE": "last_size",
        "HIGH": "high",
        "LOW": "low",
        "OPEN": "open",
        "CLOSE": "close",
        "VOLUME": "volume",
        "HALTED": "halted",
        "LAST_TIMESTAMP": "timestamp",
    }

    # ----------------------------------------------------------------
    # Contract Mapping
    # ----------------------------------------------------------------

    def to_ib_contract(self, contract: Contract) -> IBApiContract:
        """
        Convert domain Contract to IB API Contract.

        Args:
            contract: Domain contract

        Returns:
            IB API Contract
        """
        ib_contract = IBApiContract()

        ib_contract.conId = contract.con_id
        ib_contract.symbol = contract.symbol
        ib_contract.secType = contract.sec_type
        ib_contract.exchange = contract.exchange
        ib_contract.currency = contract.currency
        ib_contract.localSymbol = contract.local_symbol
        ib_contract.primaryExchange = contract.primary_exchange
        ib_contract.lastTradeDateOrContractMonth = contract.last_trade_date
        ib_contract.multiplier = contract.multiplier
        ib_contract.tradingClass = contract.trading_class
        ib_contract.includeExpired = contract.include_expired

        # Option-specific
        if contract.sec_type == "OPT":
            ib_contract.strike = contract.strike
            ib_contract.right = contract.right

        return ib_contract

    def from_ib_contract(self, ib_contract: IBApiContract) -> Contract:
        """
        Convert IB API Contract to domain Contract.

        Args:
            ib_contract: IB API Contract

        Returns:
            Domain Contract (or specialized subclass)
        """
        sec_type = getattr(ib_contract, "secType", "")

        # Create appropriate subclass
        if sec_type == "STK":
            return StockContract(
                con_id=getattr(ib_contract, "conId", 0),
                symbol=getattr(ib_contract, "symbol", ""),
                sec_type=sec_type,
                exchange=getattr(ib_contract, "exchange", "SMART"),
                currency=getattr(ib_contract, "currency", "USD"),
                local_symbol=getattr(ib_contract, "localSymbol", ""),
                primary_exchange=getattr(ib_contract, "primaryExchange", ""),
                last_trade_date=getattr(
                    ib_contract, "lastTradeDateOrContractMonth", ""
                ),
                multiplier=getattr(ib_contract, "multiplier", ""),
                trading_class=getattr(ib_contract, "tradingClass", ""),
            )
        elif sec_type == "FUT":
            return FutureContract(
                con_id=getattr(ib_contract, "conId", 0),
                symbol=getattr(ib_contract, "symbol", ""),
                sec_type=sec_type,
                exchange=getattr(ib_contract, "exchange", ""),
                currency=getattr(ib_contract, "currency", "USD"),
                local_symbol=getattr(ib_contract, "localSymbol", ""),
                primary_exchange=getattr(ib_contract, "primaryExchange", ""),
                last_trade_date=getattr(
                    ib_contract, "lastTradeDateOrContractMonth", ""
                ),
                multiplier=getattr(ib_contract, "multiplier", ""),
                trading_class=getattr(ib_contract, "tradingClass", ""),
                include_expired=getattr(ib_contract, "includeExpired", True),
            )
        elif sec_type == "OPT":
            return OptionContract(
                con_id=getattr(ib_contract, "conId", 0),
                symbol=getattr(ib_contract, "symbol", ""),
                sec_type=sec_type,
                exchange=getattr(ib_contract, "exchange", "SMART"),
                currency=getattr(ib_contract, "currency", "USD"),
                local_symbol=getattr(ib_contract, "localSymbol", ""),
                last_trade_date=getattr(
                    ib_contract, "lastTradeDateOrContractMonth", ""
                ),
                multiplier=getattr(ib_contract, "multiplier", "100"),
                strike=getattr(ib_contract, "strike", 0.0),
                right=getattr(ib_contract, "right", ""),
            )
        else:
            return Contract(
                con_id=getattr(ib_contract, "conId", 0),
                symbol=getattr(ib_contract, "symbol", ""),
                sec_type=sec_type,
                exchange=getattr(ib_contract, "exchange", ""),
                currency=getattr(ib_contract, "currency", "USD"),
                local_symbol=getattr(ib_contract, "localSymbol", ""),
                primary_exchange=getattr(ib_contract, "primaryExchange", ""),
                last_trade_date=getattr(
                    ib_contract, "lastTradeDateOrContractMonth", ""
                ),
                multiplier=getattr(ib_contract, "multiplier", ""),
                trading_class=getattr(ib_contract, "tradingClass", ""),
                include_expired=getattr(ib_contract, "includeExpired", False),
            )

    # ----------------------------------------------------------------
    # ContractDetails Mapping
    # ----------------------------------------------------------------

    def to_ib_contract_details(
        self, contract_details: ContractDetails
    ) -> IBApiContractDetails:
        """
        Convert domain ContractDetails to IB API ContractDetails.

        Args:
            contract_details: Domain contract details

        Returns:
            IB API ContractDetails
        """
        ib_cd = IBApiContractDetails()

        ib_cd.contract = self.to_ib_contract(contract_details.contract)
        ib_cd.marketName = contract_details.market_name
        ib_cd.minTick = contract_details.min_tick
        ib_cd.orderTypes = contract_details.order_types
        ib_cd.validExchanges = contract_details.valid_exchanges
        ib_cd.priceMagnifier = contract_details.price_magnifier
        ib_cd.underConId = contract_details.under_con_id
        ib_cd.longName = contract_details.long_name
        ib_cd.contractMonth = contract_details.contract_month
        ib_cd.industry = contract_details.industry
        ib_cd.category = contract_details.category
        ib_cd.subcategory = contract_details.subcategory
        ib_cd.timeZoneId = contract_details.time_zone_id
        ib_cd.tradingHours = contract_details.trading_hours
        ib_cd.liquidHours = contract_details.liquid_hours
        ib_cd.evRule = contract_details.ev_rule
        ib_cd.evMultiplier = contract_details.ev_multiplier
        ib_cd.mdSizeMultiplier = contract_details.md_size_multiplier
        ib_cd.aggGroup = contract_details.agg_group
        ib_cd.underSymbol = contract_details.under_symbol
        ib_cd.underSecType = contract_details.under_sec_type
        ib_cd.marketRuleIds = contract_details.market_rule_ids
        ib_cd.realExpirationDate = contract_details.real_expiration_date
        ib_cd.lastTradeTime = contract_details.last_trade_time
        ib_cd.stockType = contract_details.stock_type

        return ib_cd

    def from_ib_contract_details(
        self, ib_cd: IBApiContractDetails
    ) -> ContractDetails:
        """
        Convert IB API ContractDetails to domain ContractDetails.

        Args:
            ib_cd: IB API ContractDetails

        Returns:
            Domain ContractDetails
        """
        contract = self.from_ib_contract(ib_cd.contract)

        return ContractDetails(
            contract=contract,
            market_name=getattr(ib_cd, "marketName", ""),
            min_tick=getattr(ib_cd, "minTick", 0.0),
            order_types=getattr(ib_cd, "orderTypes", ""),
            valid_exchanges=getattr(ib_cd, "validExchanges", ""),
            price_magnifier=getattr(ib_cd, "priceMagnifier", 1),
            under_con_id=getattr(ib_cd, "underConId", 0),
            long_name=getattr(ib_cd, "longName", ""),
            contract_month=getattr(ib_cd, "contractMonth", ""),
            industry=getattr(ib_cd, "industry", ""),
            category=getattr(ib_cd, "category", ""),
            subcategory=getattr(ib_cd, "subcategory", ""),
            time_zone_id=getattr(ib_cd, "timeZoneId", ""),
            trading_hours=getattr(ib_cd, "tradingHours", ""),
            liquid_hours=getattr(ib_cd, "liquidHours", ""),
            ev_rule=getattr(ib_cd, "evRule", ""),
            ev_multiplier=getattr(ib_cd, "evMultiplier", 0.0),
            md_size_multiplier=getattr(ib_cd, "mdSizeMultiplier", 1),
            agg_group=getattr(ib_cd, "aggGroup", 0),
            under_symbol=getattr(ib_cd, "underSymbol", ""),
            under_sec_type=getattr(ib_cd, "underSecType", ""),
            market_rule_ids=getattr(ib_cd, "marketRuleIds", ""),
            real_expiration_date=getattr(ib_cd, "realExpirationDate", ""),
            last_trade_time=getattr(ib_cd, "lastTradeTime", ""),
            stock_type=getattr(ib_cd, "stockType", ""),
            min_size=getattr(ib_cd, "minSize", 0.0),
            size_increment=getattr(ib_cd, "sizeIncrement", 0.0),
            suggested_size_increment=getattr(ib_cd, "suggestedSizeIncrement", 0.0),
        )

    # ----------------------------------------------------------------
    # Bar Data Mapping
    # ----------------------------------------------------------------

    def from_ib_bar(self, ib_bar: Any) -> BarData:
        """
        Convert IB API BarData to domain BarData.

        Args:
            ib_bar: IB API BarData

        Returns:
            Domain BarData
        """
        # Parse date - IB uses various formats
        date_str = getattr(ib_bar, "date", "")
        dt = self._parse_ib_date(date_str)

        return BarData(
            datetime=dt,
            open=getattr(ib_bar, "open", 0.0),
            high=getattr(ib_bar, "high", 0.0),
            low=getattr(ib_bar, "low", 0.0),
            close=getattr(ib_bar, "close", 0.0),
            volume=int(getattr(ib_bar, "volume", 0)),
        )

    def from_ib_bars(self, ib_bars: List[Any]) -> List[BarData]:
        """
        Convert list of IB API BarData to domain BarData.

        Args:
            ib_bars: List of IB API BarData

        Returns:
            List of domain BarData
        """
        return [self.from_ib_bar(bar) for bar in ib_bars]

    def bar_to_tuple(
        self, bar: BarData
    ) -> Tuple[datetime, float, float, float, float, int]:
        """
        Convert BarData to tuple for compatibility with existing code.

        Args:
            bar: Domain BarData

        Returns:
            Tuple of (datetime, open, high, low, close, volume)
        """
        return bar.to_tuple()

    def bars_to_tuples(
        self, bars: List[BarData]
    ) -> List[Tuple[datetime, float, float, float, float, int]]:
        """
        Convert list of BarData to tuples.

        Args:
            bars: List of domain BarData

        Returns:
            List of tuples
        """
        return [self.bar_to_tuple(bar) for bar in bars]

    # ----------------------------------------------------------------
    # Tick Data Mapping
    # ----------------------------------------------------------------

    def from_tick_dict(self, tick_dict: Dict[str, Any]) -> TickData:
        """
        Convert tick data dictionary to domain TickData.

        Args:
            tick_dict: Dictionary with tick data

        Returns:
            Domain TickData
        """
        return TickData(
            symbol=tick_dict.get("ticker", ""),
            local_symbol=tick_dict.get("localSymbol", ""),
            bid=tick_dict.get("bid", 0.0),
            bid_size=tick_dict.get("bid_size", 0),
            ask=tick_dict.get("ask", 0.0),
            ask_size=tick_dict.get("ask_size", 0),
            last=tick_dict.get("last", 0.0),
            last_size=tick_dict.get("last_size", 0),
            volume=tick_dict.get("volume", 0),
            open=tick_dict.get("open", 0.0),
            high=tick_dict.get("high", 0.0),
            low=tick_dict.get("low", 0.0),
            close=tick_dict.get("close", 0.0),
            halted=tick_dict.get("halted", 0),
        )

    def tick_type_to_field(self, tick_type: str) -> Optional[str]:
        """
        Convert IB tick type string to field name.

        Args:
            tick_type: IB tick type string (e.g., "BID", "ASK")

        Returns:
            Field name or None if not mapped
        """
        return self.TICK_TYPE_MAPPING.get(tick_type.upper())

    # ----------------------------------------------------------------
    # Helper Methods
    # ----------------------------------------------------------------

    def _parse_ib_date(self, date_str: str) -> datetime:
        """
        Parse IB date string to timezone-aware datetime (UTC).

        IB uses various formats:
        - "20210101" (YYYYMMDD)
        - "20210101 09:30:00" (YYYYMMDD HH:MM:SS)
        - "1609459200" (Unix timestamp)

        Args:
            date_str: Date string from IB

        Returns:
            Parsed datetime with UTC timezone
        """
        if not date_str:
            return datetime.now(timezone.utc)

        try:
            # Try Unix timestamp first
            if date_str.isdigit() and len(date_str) >= 10:
                return datetime.fromtimestamp(int(date_str), tz=timezone.utc)

            # Try YYYYMMDD HH:MM:SS
            if " " in date_str:
                dt = datetime.strptime(date_str, "%Y%m%d %H:%M:%S")
                return dt.replace(tzinfo=timezone.utc)

            # Try YYYYMMDD
            if len(date_str) == 8:
                dt = datetime.strptime(date_str, "%Y%m%d")
                return dt.replace(tzinfo=timezone.utc)

            # Try ISO format
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        except (ValueError, TypeError) as e:
            log.warning(f"Failed to parse date '{date_str}': {e}")
            return datetime.now(timezone.utc)
