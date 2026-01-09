"""
Asset service implementation.

Provides business logic for asset management with dependency injection.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional

from src.core.interfaces.broker import IBrokerClient
from src.core.interfaces.repositories import IAssetRepository
from src.core.interfaces.services import IAssetService
from src.domain.entities.asset import Asset, AssetType
from src.domain.entities.contract import Contract, StockContract, FutureContract
from src.domain.entities.contract_details import ContractDetails

log = logging.getLogger("CellarLogger")


class AssetService(IAssetService):
    """
    Asset service with dependency injection.

    Provides:
    - Asset CRUD operations (via repository)
    - Contract details fetching (via broker client)

    Example:
        service = AssetService(
            asset_repository=JsonAssetRepository("/path"),
            broker_client=ib_client,
        )
        asset = service.get_asset("STOCK", "AAPL")
    """

    def __init__(
        self,
        asset_repository: IAssetRepository,
        broker_client: Optional[IBrokerClient] = None,
    ):
        """
        Initialize service.

        Args:
            asset_repository: Repository for asset persistence
            broker_client: Optional broker client for contract details
        """
        self._repository = asset_repository
        self._broker = broker_client
        log.info("AssetService initialized")

    # ----------------------------------------------------------------
    # IAssetService Implementation
    # ----------------------------------------------------------------

    def get_asset(self, asset_type: str, symbol: str) -> Optional[Asset]:
        """
        Get an asset by type and symbol.

        Args:
            asset_type: Type of asset ("STOCK", "FUTURE", etc.)
            symbol: Asset symbol

        Returns:
            Asset object or None if not found
        """
        data = self._repository.get(asset_type, symbol)

        if data is None:
            log.debug(f"Asset not found: {asset_type}/{symbol}")
            return None

        return self._dict_to_asset(data)

    def get_all_assets(self, asset_type: str) -> List[Asset]:
        """
        Get all assets of a given type.

        Args:
            asset_type: Type of asset

        Returns:
            List of Asset objects
        """
        data_list = self._repository.get_all(asset_type)
        return [self._dict_to_asset(data) for data in data_list]

    def save_asset(self, asset: Asset) -> None:
        """
        Save or update an asset.

        Args:
            asset: Asset object to save
        """
        data = self._asset_to_dict(asset)
        self._repository.save(data)
        log.info(f"Asset saved: {asset.asset_type.value}/{asset.symbol}")

    def delete_asset(self, asset_type: str, symbol: str) -> None:
        """
        Delete an asset.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
        """
        self._repository.delete(asset_type, symbol)
        log.info(f"Asset deleted: {asset_type}/{symbol}")

    def exists(self, asset_type: str, symbol: str) -> bool:
        """
        Check if an asset exists.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            True if asset exists
        """
        return self._repository.exists(asset_type, symbol)

    def fetch_contract_details(
        self,
        asset_type: str,
        contract: Contract,
        callback: Optional[Callable[[List[ContractDetails]], None]] = None,
    ) -> int:
        """
        Fetch contract details from broker.

        Args:
            asset_type: Type of asset
            contract: Domain Contract object
            callback: Called with list of ContractDetails

        Returns:
            Request ID
        """
        if self._broker is None:
            raise RuntimeError("Broker client not configured")

        collected_details: List[ContractDetails] = []
        details_lock = threading.Lock()

        def on_details(details: ContractDetails):
            with details_lock:
                if details is not None:
                    collected_details.append(details)

        # Request from broker
        req_id = self._broker.get_contract_details(contract, on_details)

        # For stocks, details come quickly; for futures, may take longer
        # The callback pattern handles this asynchronously
        if callback:
            # Set up a delayed callback after collection period
            def delayed_callback():
                import time
                # Wait for details to arrive
                wait_time = 2.0 if asset_type == "FUTURE" else 1.0
                time.sleep(wait_time)
                with details_lock:
                    callback(collected_details.copy())

            thread = threading.Thread(target=delayed_callback, daemon=True)
            thread.start()

        return req_id

    def get_latest_contract_details(
        self, asset_type: str, symbol: str, count: int = 1
    ) -> List[ContractDetails]:
        """
        Get the latest contract details from stored asset.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
            count: Number of latest contracts to return

        Returns:
            List of ContractDetails (for futures, sorted by expiration)
        """
        asset = self.get_asset(asset_type, symbol)
        if asset is None:
            return []

        if not asset.contract_details:
            return []

        # Sort by last trade date for futures
        sorted_details = sorted(
            asset.contract_details,
            key=lambda cd: cd.contract.last_trade_date or "",
            reverse=True,
        )

        return sorted_details[:count]

    def add_contract_to_asset(
        self, asset: Asset, contract_details: ContractDetails
    ) -> None:
        """
        Add a contract to an asset and save.

        Args:
            asset: Asset to add contract to
            contract_details: ContractDetails to add

        Note:
            Skips if contract with same local_symbol already exists.
        """
        # Check if contract already exists
        existing_symbols = {
            cd.contract.local_symbol for cd in asset.contract_details
        }
        if contract_details.contract.local_symbol in existing_symbols:
            log.warning(
                f"Contract {contract_details.contract.local_symbol} already exists in {asset.symbol}"
            )
            return

        # Add contract and save
        asset.contract_details.append(contract_details)
        self.save_asset(asset)
        log.info(
            f"Added contract {contract_details.contract.local_symbol} to {asset.symbol}"
        )

    def remove_contract_from_asset(
        self, asset: Asset, local_symbol: str
    ) -> bool:
        """
        Remove a contract from an asset and save.

        Args:
            asset: Asset to remove contract from
            local_symbol: Local symbol of the contract to remove

        Returns:
            True if contract was found and removed, False otherwise
        """
        original_count = len(asset.contract_details)
        asset.contract_details = [
            cd
            for cd in asset.contract_details
            if cd.contract.local_symbol != local_symbol
        ]

        if len(asset.contract_details) < original_count:
            self.save_asset(asset)
            log.info(f"Removed contract {local_symbol} from {asset.symbol}")
            return True
        else:
            log.warning(f"Contract {local_symbol} not found in {asset.symbol}")
            return False

    # ----------------------------------------------------------------
    # Helper Methods
    # ----------------------------------------------------------------

    def _dict_to_asset(self, data: Dict[str, Any]) -> Asset:
        """Convert dictionary to Asset object."""
        # Support both snake_case and camelCase keys (JSON uses camelCase)
        asset_type_str = data.get("type") or data.get("asset_type", "STOCK")
        asset_type = AssetType.from_str(asset_type_str)

        # Convert contract details - support both key formats
        contract_details = []
        cd_list = data.get("contractDetails") or data.get("contract_details", [])

        log.info(f"Loading asset {data.get('symbol')}: cd_list count = {len(cd_list)}")
        for cd_data in cd_list:
            contract_details.append(self._dict_to_contract_details(cd_data))

        log.info(f"  Converted contract_details count: {len(contract_details)}")

        return Asset(
            symbol=data.get("symbol", ""),
            asset_type=asset_type,
            short_description=data.get("shortDescription") or data.get("short_description", ""),
            contract_details=contract_details,
        )

    def _asset_to_dict(self, asset: Asset) -> Dict[str, Any]:
        """Convert Asset object to dictionary."""
        return {
            "symbol": asset.symbol,
            "asset_type": asset.asset_type.value,
            "contract_details": [
                self._contract_details_to_dict(cd)
                for cd in asset.contract_details
            ],
        }

    def _dict_to_contract_details(self, data: Dict[str, Any]) -> ContractDetails:
        """Convert dictionary to ContractDetails."""
        contract_data = data.get("contract", {})
        # Support both camelCase (JSON) and snake_case keys
        sec_type = contract_data.get("secType") or contract_data.get("sec_type", "STK")

        # Helper to get value with camelCase or snake_case key
        def get_contract_val(camel: str, snake: str, default=""):
            return contract_data.get(camel) or contract_data.get(snake, default)

        # Create appropriate contract type
        if sec_type == "STK":
            contract = StockContract(
                con_id=get_contract_val("conId", "con_id", 0),
                symbol=get_contract_val("symbol", "symbol", ""),
                sec_type=sec_type,
                exchange=get_contract_val("exchange", "exchange", "SMART"),
                currency=get_contract_val("currency", "currency", "USD"),
                local_symbol=get_contract_val("localSymbol", "local_symbol", ""),
                primary_exchange=get_contract_val("primaryExchange", "primary_exchange", ""),
            )
        elif sec_type == "FUT":
            contract = FutureContract(
                con_id=get_contract_val("conId", "con_id", 0),
                symbol=get_contract_val("symbol", "symbol", ""),
                sec_type=sec_type,
                exchange=get_contract_val("exchange", "exchange", ""),
                currency=get_contract_val("currency", "currency", "USD"),
                local_symbol=get_contract_val("localSymbol", "local_symbol", ""),
                last_trade_date=get_contract_val("lastTradeDateOrContractMonth", "last_trade_date", ""),
                multiplier=get_contract_val("multiplier", "multiplier", ""),
            )
        else:
            contract = Contract(
                con_id=get_contract_val("conId", "con_id", 0),
                symbol=get_contract_val("symbol", "symbol", ""),
                sec_type=sec_type,
                exchange=get_contract_val("exchange", "exchange", ""),
                currency=get_contract_val("currency", "currency", "USD"),
            )

        # Helper for contract details fields
        def get_cd_val(camel: str, snake: str, default=""):
            return data.get(camel) or data.get(snake, default)

        return ContractDetails(
            contract=contract,
            market_name=get_cd_val("marketName", "market_name", ""),
            min_tick=get_cd_val("minTick", "min_tick", 0.0),
            long_name=get_cd_val("longName", "long_name", ""),
            contract_month=get_cd_val("contractMonth", "contract_month", ""),
            time_zone_id=get_cd_val("timeZoneId", "time_zone_id", ""),
            trading_hours=get_cd_val("tradingHours", "trading_hours", ""),
            liquid_hours=get_cd_val("liquidHours", "liquid_hours", ""),
        )

    def _contract_details_to_dict(self, cd: ContractDetails) -> Dict[str, Any]:
        """Convert ContractDetails to dictionary."""
        return {
            "contract": {
                "con_id": cd.contract.con_id,
                "symbol": cd.contract.symbol,
                "sec_type": cd.contract.sec_type,
                "exchange": cd.contract.exchange,
                "currency": cd.contract.currency,
                "local_symbol": cd.contract.local_symbol,
                "primary_exchange": cd.contract.primary_exchange,
                "last_trade_date": cd.contract.last_trade_date,
                "multiplier": cd.contract.multiplier,
                "trading_class": cd.contract.trading_class,
            },
            "market_name": cd.market_name,
            "min_tick": cd.min_tick,
            "long_name": cd.long_name,
            "contract_month": cd.contract_month,
            "time_zone_id": cd.time_zone_id,
            "trading_hours": cd.trading_hours,
            "liquid_hours": cd.liquid_hours,
        }
