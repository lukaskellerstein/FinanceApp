"""
JSON file-based asset repository implementation.

Implements IAssetRepository interface with per-asset JSON files.
"""

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

from src.core.interfaces.repositories import IAssetRepository
from src.domain.entities.asset import AssetType

log = logging.getLogger("CellarLogger")


class JsonAssetRepository(IAssetRepository):
    """
    JSON file-based asset repository.

    Stores each asset as a separate JSON file organized by asset type.

    File structure:
        {base_path}/stocks/{symbol}.json
        {base_path}/futures/{symbol}.json

    Example:
        repo = JsonAssetRepository("/path/to/assets")
        repo.save({"symbol": "AAPL", "asset_type": "STOCK", ...})
        asset = repo.get("STOCK", "AAPL")
    """

    # Mapping from asset type string to directory name
    TYPE_DIR_MAP = {
        "STOCK": "stocks",
        "FUTURE": "futures",
        "OPTION": "options",
        "INDEX": "indices",
        "FOREX": "forex",
        "CRYPTO": "crypto",
    }

    def __init__(self, base_path: str):
        """
        Initialize repository.

        Args:
            base_path: Base directory for asset storage
        """
        self.base_path = base_path
        self.lock = threading.Lock()
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create asset directories if they don't exist."""
        for dir_name in self.TYPE_DIR_MAP.values():
            dir_path = os.path.join(self.base_path, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

    def _get_type_directory(self, asset_type: str) -> str:
        """
        Get directory path for an asset type.

        Args:
            asset_type: Asset type string (e.g., "STOCK")

        Returns:
            Directory path
        """
        dir_name = self.TYPE_DIR_MAP.get(asset_type.upper(), "unknown")
        return os.path.join(self.base_path, dir_name)

    def _get_file_path(self, asset_type: str, symbol: str) -> str:
        """
        Get full path for an asset's JSON file.

        Args:
            asset_type: Asset type string
            symbol: Asset symbol

        Returns:
            Full file path
        """
        dir_path = self._get_type_directory(asset_type)
        return os.path.join(dir_path, f"{symbol}.json")

    def _read_json_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Read and parse a JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed dictionary or None
        """
        if not os.path.exists(file_path):
            return None

        with self.lock:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                log.error(f"JSON decode error in {file_path}: {e}")
                return None
            except Exception as e:
                log.error(f"Error reading {file_path}: {e}")
                raise

    def _write_json_file(self, file_path: str, data: Dict[str, Any]) -> None:
        """
        Write data to a JSON file.

        Args:
            file_path: Path to JSON file
            data: Data to write
        """
        with self.lock:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            except Exception as e:
                log.error(f"Error writing {file_path}: {e}")
                raise

    def _delete_json_file(self, file_path: str) -> None:
        """
        Delete a JSON file.

        Args:
            file_path: Path to JSON file
        """
        if not os.path.exists(file_path):
            log.warning(f"File does not exist: {file_path}")
            return

        with self.lock:
            try:
                os.remove(file_path)
            except Exception as e:
                log.error(f"Error deleting {file_path}: {e}")
                raise

    # ----------------------------------------------------------------
    # IAssetRepository Implementation
    # ----------------------------------------------------------------

    def get(self, asset_type: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get an asset by type and symbol.

        Args:
            asset_type: Type of asset (e.g., "STOCK", "FUTURE")
            symbol: Asset symbol

        Returns:
            Asset dictionary or None if not found
        """
        file_path = self._get_file_path(asset_type, symbol)
        return self._read_json_file(file_path)

    def get_all(self, asset_type: str) -> List[Dict[str, Any]]:
        """
        Get all assets of a given type.

        Args:
            asset_type: Type of asset

        Returns:
            List of asset dictionaries
        """
        dir_path = self._get_type_directory(asset_type)
        result: List[Dict[str, Any]] = []

        if not os.path.exists(dir_path):
            return result

        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                file_path = os.path.join(dir_path, filename)
                asset = self._read_json_file(file_path)
                if asset:
                    result.append(asset)

        return result

    def save(self, asset: Dict[str, Any]) -> None:
        """
        Save or update an asset.

        Args:
            asset: Asset dictionary to save (must have 'symbol' and 'asset_type')
        """
        symbol = asset.get("symbol")
        asset_type = asset.get("asset_type", "STOCK")

        if not symbol:
            raise ValueError("Asset must have a 'symbol' field")

        file_path = self._get_file_path(asset_type, symbol)
        self._write_json_file(file_path, asset)
        log.info(f"Asset saved: {file_path}")

    def delete(self, asset_type: str, symbol: str) -> None:
        """
        Delete an asset.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
        """
        file_path = self._get_file_path(asset_type, symbol)
        self._delete_json_file(file_path)
        log.info(f"Asset deleted: {file_path}")

    def exists(self, asset_type: str, symbol: str) -> bool:
        """
        Check if an asset exists.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            True if asset exists
        """
        file_path = self._get_file_path(asset_type, symbol)
        return os.path.exists(file_path)

    def find_by_criteria(
        self, asset_type: str, criteria: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Find asset by arbitrary criteria (scans all files).

        Args:
            asset_type: Type of asset
            criteria: Dictionary of field/value pairs to match

        Returns:
            First matching asset or None
        """
        dir_path = self._get_type_directory(asset_type)

        if not os.path.exists(dir_path):
            return None

        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                file_path = os.path.join(dir_path, filename)
                asset = self._read_json_file(file_path)
                if asset and self._matches_criteria(asset, criteria):
                    return asset

        return None

    def _matches_criteria(
        self, asset: Dict[str, Any], criteria: Dict[str, Any]
    ) -> bool:
        """Check if asset matches all criteria."""
        for key, value in criteria.items():
            if asset.get(key) != value:
                return False
        return True
