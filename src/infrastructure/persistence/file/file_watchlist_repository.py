"""
File-based watchlist repository implementation.

Implements IWatchlistRepository using JSON files for multi-watchlist storage.
Supports migration from legacy text files.
"""

import json
import logging
import os
import shutil
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.interfaces.repositories import IWatchlistRepository

log = logging.getLogger("CellarLogger")


class FileWatchlistRepository(IWatchlistRepository):
    """
    File-based watchlist repository with multi-watchlist support.

    Storage format (JSON):
        {base_path}/stock_watchlists.json
        {base_path}/future_watchlists.json

    JSON structure:
        {
            "watchlists": [
                {"id": "uuid", "name": "Default", "symbols": [...], ...}
            ],
            "active_watchlist_id": "uuid"
        }

    Legacy format (text, for migration):
        {base_path}/stock.txt
        {base_path}/future.txt
    """

    def __init__(self, base_path: str):
        """
        Initialize repository.

        Args:
            base_path: Base directory for watchlist files
        """
        self.base_path = base_path
        self.lock = threading.Lock()
        self._ensure_directory()
        self._migrate_legacy_files()

    def _ensure_directory(self) -> None:
        """Create base directory if it doesn't exist."""
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)

    def _get_json_path(self, asset_type: str) -> str:
        """Get JSON file path for an asset type."""
        return os.path.join(self.base_path, f"{asset_type}_watchlists.json")

    def _get_legacy_path(self, watchlist_name: str) -> str:
        """Get legacy text file path."""
        return os.path.join(self.base_path, f"{watchlist_name}.txt")

    def _migrate_legacy_files(self) -> None:
        """Migrate legacy .txt files to new JSON format."""
        for asset_type in ["stock", "future"]:
            json_path = self._get_json_path(asset_type)
            legacy_path = self._get_legacy_path(asset_type)

            # Skip if JSON already exists or legacy doesn't exist
            if os.path.exists(json_path) or not os.path.exists(legacy_path):
                continue

            log.info(f"Migrating legacy watchlist: {legacy_path} -> {json_path}")

            try:
                # Read legacy symbols
                symbols = self._read_legacy_symbols(legacy_path)

                # Create new JSON structure with default watchlist
                data = {
                    "watchlists": [
                        {
                            "id": str(uuid.uuid4()),
                            "name": "Default",
                            "symbols": symbols,
                            "asset_type": asset_type,
                            "created_at": datetime.now().isoformat(),
                            "is_default": True,
                        }
                    ],
                    "active_watchlist_id": None,  # Will be set to first watchlist
                }
                data["active_watchlist_id"] = data["watchlists"][0]["id"]

                # Write JSON file
                self._write_json(json_path, data)

                # Backup legacy file
                backup_path = legacy_path + ".bak"
                shutil.move(legacy_path, backup_path)
                log.info(f"Migration complete. Backup at: {backup_path}")

            except Exception as e:
                log.error(f"Migration failed for {asset_type}: {e}")

    def _read_legacy_symbols(self, file_path: str) -> List[str]:
        """Read symbols from legacy text file."""
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            log.error(f"Error reading legacy file {file_path}: {e}")
            return []

    def _read_json(self, file_path: str) -> Dict[str, Any]:
        """Read JSON data from file."""
        if not os.path.exists(file_path):
            return {"watchlists": [], "active_watchlist_id": None}

        with self.lock:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                log.error(f"Error reading JSON {file_path}: {e}")
                return {"watchlists": [], "active_watchlist_id": None}

    def _write_json(self, file_path: str, data: Dict[str, Any]) -> None:
        """Write JSON data to file."""
        with self.lock:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                log.error(f"Error writing JSON {file_path}: {e}")
                raise

    def _ensure_default_watchlist(
        self, asset_type: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ensure at least one watchlist exists, creating default if needed."""
        if not data["watchlists"]:
            default_id = str(uuid.uuid4())
            data["watchlists"].append(
                {
                    "id": default_id,
                    "name": "Default",
                    "symbols": [],
                    "asset_type": asset_type,
                    "created_at": datetime.now().isoformat(),
                    "is_default": True,
                }
            )
            data["active_watchlist_id"] = default_id
            self._write_json(self._get_json_path(asset_type), data)
        return data

    # ----------------------------------------------------------------
    # Legacy single-watchlist methods (backward compatibility)
    # These operate on the active watchlist
    # ----------------------------------------------------------------

    def get(self, watchlist_name: str) -> List[str]:
        """
        Get symbols in the active watchlist for an asset type.

        Args:
            watchlist_name: Asset type (e.g., "stock", "future")

        Returns:
            List of symbols from the active watchlist
        """
        start = time.time()
        data = self._read_json(self._get_json_path(watchlist_name))
        data = self._ensure_default_watchlist(watchlist_name, data)

        # Get active watchlist
        active_id = data.get("active_watchlist_id")
        for wl in data["watchlists"]:
            if wl["id"] == active_id:
                symbols = wl.get("symbols", [])
                elapsed = time.time() - start
                log.info(
                    f"Loaded watchlist '{wl['name']}' ({len(symbols)} symbols) "
                    f"in {elapsed:.3f}s"
                )
                return symbols

        # Fallback to first watchlist
        if data["watchlists"]:
            return data["watchlists"][0].get("symbols", [])
        return []

    def add_symbol(self, watchlist_name: str, symbol: str) -> None:
        """Add symbol to active watchlist."""
        json_path = self._get_json_path(watchlist_name)
        data = self._read_json(json_path)
        data = self._ensure_default_watchlist(watchlist_name, data)

        active_id = data.get("active_watchlist_id")
        for wl in data["watchlists"]:
            if wl["id"] == active_id:
                if symbol not in wl["symbols"]:
                    wl["symbols"].append(symbol)
                    self._write_json(json_path, data)
                    log.info(f"Added {symbol} to {wl['name']}")
                return

    def remove_symbol(self, watchlist_name: str, symbol: str) -> None:
        """Remove symbol from active watchlist."""
        json_path = self._get_json_path(watchlist_name)
        data = self._read_json(json_path)

        active_id = data.get("active_watchlist_id")
        for wl in data["watchlists"]:
            if wl["id"] == active_id:
                if symbol in wl["symbols"]:
                    wl["symbols"].remove(symbol)
                    self._write_json(json_path, data)
                    log.info(f"Removed {symbol} from {wl['name']}")
                return

    def update(self, watchlist_name: str, symbols: List[str]) -> None:
        """Replace symbols in active watchlist."""
        json_path = self._get_json_path(watchlist_name)
        data = self._read_json(json_path)
        data = self._ensure_default_watchlist(watchlist_name, data)

        active_id = data.get("active_watchlist_id")
        for wl in data["watchlists"]:
            if wl["id"] == active_id:
                wl["symbols"] = symbols.copy()
                self._write_json(json_path, data)
                log.info(f"Updated {wl['name']} with {len(symbols)} symbols")
                return

    def exists(self, watchlist_name: str) -> bool:
        """Check if any watchlists exist for asset type."""
        json_path = self._get_json_path(watchlist_name)
        if os.path.exists(json_path):
            data = self._read_json(json_path)
            return len(data.get("watchlists", [])) > 0
        # Check legacy path
        return os.path.exists(self._get_legacy_path(watchlist_name))

    def delete(self, watchlist_name: str) -> None:
        """Delete JSON file for asset type (use delete_watchlist for specific)."""
        json_path = self._get_json_path(watchlist_name)
        if os.path.exists(json_path):
            with self.lock:
                os.remove(json_path)
                log.info(f"Deleted watchlist file {watchlist_name}")

    def list_watchlists(self) -> List[str]:
        """List all asset types with watchlists."""
        result = []
        for filename in os.listdir(self.base_path):
            if filename.endswith("_watchlists.json"):
                result.append(filename.replace("_watchlists.json", ""))
            elif filename.endswith(".txt") and not filename.endswith(".bak"):
                result.append(filename[:-4])
        return sorted(set(result))

    # ----------------------------------------------------------------
    # Multi-watchlist methods
    # ----------------------------------------------------------------

    def get_all_watchlists(self, asset_type: str) -> List[Dict[str, Any]]:
        """Get all watchlists for an asset type."""
        data = self._read_json(self._get_json_path(asset_type))
        data = self._ensure_default_watchlist(asset_type, data)
        return data.get("watchlists", [])

    def get_watchlist_by_id(
        self, asset_type: str, watchlist_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific watchlist by ID."""
        data = self._read_json(self._get_json_path(asset_type))
        for wl in data.get("watchlists", []):
            if wl["id"] == watchlist_id:
                return wl
        return None

    def create_watchlist(
        self, asset_type: str, name: str, symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new watchlist."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        new_watchlist = {
            "id": str(uuid.uuid4()),
            "name": name,
            "symbols": symbols.copy() if symbols else [],
            "asset_type": asset_type,
            "created_at": datetime.now().isoformat(),
            "is_default": len(data.get("watchlists", [])) == 0,
        }

        if "watchlists" not in data:
            data["watchlists"] = []
        data["watchlists"].append(new_watchlist)

        # Set as active if it's the first one
        if data.get("active_watchlist_id") is None:
            data["active_watchlist_id"] = new_watchlist["id"]

        self._write_json(json_path, data)
        log.info(f"Created watchlist '{name}' for {asset_type}")
        return new_watchlist

    def delete_watchlist(self, asset_type: str, watchlist_id: str) -> bool:
        """Delete a watchlist by ID."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        watchlists = data.get("watchlists", [])
        for i, wl in enumerate(watchlists):
            if wl["id"] == watchlist_id:
                deleted_name = wl["name"]
                watchlists.pop(i)

                # Update active watchlist if we deleted it
                if data.get("active_watchlist_id") == watchlist_id:
                    data["active_watchlist_id"] = (
                        watchlists[0]["id"] if watchlists else None
                    )

                self._write_json(json_path, data)
                log.info(f"Deleted watchlist '{deleted_name}'")
                return True

        return False

    def rename_watchlist(
        self, asset_type: str, watchlist_id: str, new_name: str
    ) -> bool:
        """Rename a watchlist."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        for wl in data.get("watchlists", []):
            if wl["id"] == watchlist_id:
                old_name = wl["name"]
                wl["name"] = new_name
                self._write_json(json_path, data)
                log.info(f"Renamed watchlist '{old_name}' to '{new_name}'")
                return True

        return False

    def add_symbol_to_watchlist(
        self, asset_type: str, watchlist_id: str, symbol: str
    ) -> bool:
        """Add a symbol to a specific watchlist."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        for wl in data.get("watchlists", []):
            if wl["id"] == watchlist_id:
                if symbol not in wl["symbols"]:
                    wl["symbols"].append(symbol)
                    self._write_json(json_path, data)
                    log.info(f"Added {symbol} to '{wl['name']}'")
                    return True
                return False  # Symbol already exists

        return False  # Watchlist not found

    def remove_symbol_from_watchlist(
        self, asset_type: str, watchlist_id: str, symbol: str
    ) -> bool:
        """Remove a symbol from a specific watchlist."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        for wl in data.get("watchlists", []):
            if wl["id"] == watchlist_id:
                if symbol in wl["symbols"]:
                    wl["symbols"].remove(symbol)
                    self._write_json(json_path, data)
                    log.info(f"Removed {symbol} from '{wl['name']}'")
                    return True
                return False  # Symbol not in list

        return False  # Watchlist not found

    def add_symbols_to_watchlist(
        self, asset_type: str, watchlist_id: str, symbols: List[str]
    ) -> int:
        """Add multiple symbols to a watchlist."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        for wl in data.get("watchlists", []):
            if wl["id"] == watchlist_id:
                added_count = 0
                for symbol in symbols:
                    if symbol not in wl["symbols"]:
                        wl["symbols"].append(symbol)
                        added_count += 1

                if added_count > 0:
                    self._write_json(json_path, data)
                    log.info(f"Added {added_count} symbols to '{wl['name']}'")
                return added_count

        return 0  # Watchlist not found

    def get_active_watchlist_id(self, asset_type: str) -> Optional[str]:
        """Get the ID of the active watchlist."""
        data = self._read_json(self._get_json_path(asset_type))
        return data.get("active_watchlist_id")

    def set_active_watchlist_id(
        self, asset_type: str, watchlist_id: str
    ) -> bool:
        """Set the active watchlist."""
        json_path = self._get_json_path(asset_type)
        data = self._read_json(json_path)

        # Verify watchlist exists
        for wl in data.get("watchlists", []):
            if wl["id"] == watchlist_id:
                data["active_watchlist_id"] = watchlist_id
                self._write_json(json_path, data)
                log.info(f"Set active watchlist to '{wl['name']}'")
                return True

        return False
