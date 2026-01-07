import json
import logging
import os
import threading
from typing import Any, Dict, List, Union

from src.business.model.asset import AssetType
from src.utils import files

# create logger
log = logging.getLogger("CellarLogger")


class JsonAssetService:
    """
    JSON file-based asset storage service.
    Replaces MongoAssetService with per-asset JSON files.

    File structure:
        db/assets/stocks/{symbol}.json
        db/assets/futures/{symbol}.json
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.base_path = files.get_full_path("src/db/assets")

        # Ensure base directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Create asset directories if they don't exist."""
        for asset_type in [AssetType.STOCK, AssetType.FUTURE]:
            dir_path = self._get_asset_type_directory(asset_type)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)

    def _get_asset_type_directory(self, asset_type: AssetType) -> str:
        """
        Map AssetType to directory path.

        AssetType.STOCK -> db/assets/stocks/
        AssetType.FUTURE -> db/assets/futures/
        """
        type_dir_map = {
            AssetType.STOCK: "stocks",
            AssetType.FUTURE: "futures",
        }
        return os.path.join(
            self.base_path, type_dir_map.get(asset_type, "unknown")
        )

    def _get_file_path(self, asset_type: AssetType, symbol: str) -> str:
        """Get full path for an asset's JSON file."""
        dir_path = self._get_asset_type_directory(asset_type)
        return os.path.join(dir_path, f"{symbol}.json")

    def _read_json_file(self, file_path: str) -> Union[Dict[str, Any], None]:
        """Read and parse a JSON file with thread safety."""
        if not os.path.exists(file_path):
            return None

        self.lock.acquire()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error in {file_path}: {e}")
            return None
        except Exception as e:
            log.error(f"Error reading {file_path}: {e}")
            raise
        finally:
            self.lock.release()

    def _write_json_file(self, file_path: str, data: Dict[str, Any]):
        """Write data to a JSON file with thread safety."""
        self.lock.acquire()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Error writing {file_path}: {e}")
            raise
        finally:
            self.lock.release()

    def _delete_json_file(self, file_path: str):
        """Delete a JSON file with thread safety."""
        if not os.path.exists(file_path):
            log.warning(f"File does not exist: {file_path}")
            return

        self.lock.acquire()
        try:
            os.remove(file_path)
        except Exception as e:
            log.error(f"Error deleting {file_path}: {e}")
            raise
        finally:
            self.lock.release()

    # -----------------------------------------------------------------
    # Public API (matches MongoAssetService)
    # -----------------------------------------------------------------

    def add(self, asset_type: AssetType, asset: Dict[str, Any]):
        """
        Add/save an asset to JSON file.

        Args:
            asset_type: The type of asset (STOCK or FUTURE)
            asset: Dictionary containing asset data (must have 'symbol' key)
        """
        symbol = asset.get("symbol")
        if not symbol:
            raise ValueError("Asset must have a 'symbol' field")

        file_path = self._get_file_path(asset_type, symbol)
        self._write_json_file(file_path, asset)
        log.info(f"Asset saved: {file_path}")

    def findOne(
        self, asset_type: AssetType, find_object: Dict[str, str]
    ) -> Union[Dict[str, Any], None]:
        """
        Find a single asset by search criteria.

        Args:
            asset_type: The type of asset (STOCK or FUTURE)
            find_object: Dictionary with search criteria, e.g., {"symbol": "AAPL"}

        Returns:
            Asset dictionary if found, None otherwise
        """
        symbol = find_object.get("symbol")
        if not symbol:
            # For non-symbol searches, scan all files (less efficient)
            return self._find_by_scan(asset_type, find_object)

        file_path = self._get_file_path(asset_type, symbol)
        return self._read_json_file(file_path)

    def _find_by_scan(
        self, asset_type: AssetType, find_object: Dict[str, str]
    ) -> Union[Dict[str, Any], None]:
        """
        Find asset by scanning all files (fallback for non-symbol searches).
        """
        dir_path = self._get_asset_type_directory(asset_type)

        if not os.path.exists(dir_path):
            return None

        for filename in os.listdir(dir_path):
            if filename.endswith(".json"):
                file_path = os.path.join(dir_path, filename)
                asset = self._read_json_file(file_path)
                if asset and self._matches_criteria(asset, find_object):
                    return asset

        return None

    def _matches_criteria(
        self, asset: Dict[str, Any], criteria: Dict[str, str]
    ) -> bool:
        """Check if asset matches all search criteria."""
        for key, value in criteria.items():
            if asset.get(key) != value:
                return False
        return True

    def getAll(self, asset_type: AssetType) -> List[Dict[str, Any]]:
        """
        Get all assets of a specific type.

        Args:
            asset_type: The type of asset (STOCK or FUTURE)

        Returns:
            List of asset dictionaries
        """
        dir_path = self._get_asset_type_directory(asset_type)
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

    def remove(self, asset_type: AssetType, find_object: Dict[str, str]):
        """
        Remove an asset by search criteria.

        Args:
            asset_type: The type of asset (STOCK or FUTURE)
            find_object: Dictionary with search criteria, e.g., {"symbol": "AAPL"}
        """
        symbol = find_object.get("symbol")
        if not symbol:
            log.warning("Remove requires 'symbol' in find_object")
            return

        file_path = self._get_file_path(asset_type, symbol)
        self._delete_json_file(file_path)
        log.info(f"Asset removed: {file_path}")

    # -----------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------

    def __del__(self):
        log.info("JsonAssetService destroyed")
