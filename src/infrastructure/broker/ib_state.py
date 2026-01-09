"""
IB Client request state management.

Extracted from singleton pattern to be injectable and testable.
Manages the mapping between request IDs, observables, and contracts.
"""

from __future__ import annotations
import logging
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.domain.entities.contract import Contract

log = logging.getLogger("CellarLogger")


@dataclass
class RequestInfo:
    """Information about an active request."""

    req_id: int
    symbol: str = ""
    local_symbol: str = ""
    observable_name: str = ""
    callback: Optional[Callable[[Any], None]] = None


class IBState:
    """
    Manages IB client request state.

    Thread-safe state management for:
    - Request ID generation and tracking
    - Observable/callback registration per request
    - Contract-to-request mapping
    - Temporary data accumulation for historical requests

    This class is injectable (not a singleton) for better testability.

    Example:
        state = IBState()
        req_id = state.next_request_id()
        state.register_callback(req_id, my_callback)
        state.register_contract(req_id, contract, "tickPrice")
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._req_id_counter = 0

        # Active requests: req_id -> RequestInfo
        self._requests: Dict[int, RequestInfo] = {}

        # Callbacks: req_id -> callback function
        self._callbacks: Dict[int, Callable[[Any], None]] = defaultdict(lambda: None)

        # Temporary data for accumulating results (e.g., historical bars)
        self._temp_data: Dict[int, List[Any]] = {}

        # Contract lookup: (symbol, local_symbol, observable_name) -> req_id
        self._contract_map: Dict[Tuple[str, str, str], int] = {}

    def next_request_id(self) -> int:
        """
        Generate the next unique request ID.

        Returns:
            Unique integer request ID
        """
        with self._lock:
            self._req_id_counter += 1
            return self._req_id_counter

    # ----------------------------------------------------------------
    # Callback Management
    # ----------------------------------------------------------------

    def register_callback(
        self, req_id: int, callback: Callable[[Any], None]
    ) -> None:
        """
        Register a callback for a request ID.

        Args:
            req_id: Request ID
            callback: Function to call with data
        """
        with self._lock:
            self._callbacks[req_id] = callback
            if req_id not in self._requests:
                self._requests[req_id] = RequestInfo(req_id=req_id)
            self._requests[req_id].callback = callback

    def get_callback(self, req_id: int) -> Optional[Callable[[Any], None]]:
        """
        Get the callback for a request ID.

        Args:
            req_id: Request ID

        Returns:
            Callback function or None
        """
        with self._lock:
            return self._callbacks.get(req_id)

    def unregister_callback(self, req_id: int) -> None:
        """
        Remove a callback registration.

        Args:
            req_id: Request ID
        """
        with self._lock:
            self._callbacks.pop(req_id, None)
            if req_id in self._requests:
                self._requests[req_id].callback = None

    # ----------------------------------------------------------------
    # Contract Mapping
    # ----------------------------------------------------------------

    def register_contract(
        self, req_id: int, contract: Contract, observable_name: str
    ) -> None:
        """
        Register a contract for a request.

        Args:
            req_id: Request ID
            contract: Domain Contract
            observable_name: Name of the observable type (e.g., "tickPrice")
        """
        with self._lock:
            key = (contract.symbol, contract.local_symbol, observable_name)
            self._contract_map[key] = req_id

            if req_id not in self._requests:
                self._requests[req_id] = RequestInfo(req_id=req_id)

            self._requests[req_id].symbol = contract.symbol
            self._requests[req_id].local_symbol = contract.local_symbol
            self._requests[req_id].observable_name = observable_name

    def get_request_for_contract(
        self, contract: Contract, observable_name: str
    ) -> Optional[int]:
        """
        Get request ID for a contract if one exists.

        Args:
            contract: Domain Contract
            observable_name: Observable type name

        Returns:
            Request ID or None
        """
        with self._lock:
            key = (contract.symbol, contract.local_symbol, observable_name)
            return self._contract_map.get(key)

    def get_or_create_request_for_contract(
        self, contract: Contract, observable_name: str
    ) -> Tuple[bool, int]:
        """
        Get existing request ID or create a new one for a contract.

        Args:
            contract: Domain Contract
            observable_name: Observable type name

        Returns:
            Tuple of (already_existed, req_id)
        """
        with self._lock:
            key = (contract.symbol, contract.local_symbol, observable_name)

            if key in self._contract_map:
                return (True, self._contract_map[key])

            # Create new request
            self._req_id_counter += 1
            req_id = self._req_id_counter

            self._contract_map[key] = req_id
            self._requests[req_id] = RequestInfo(
                req_id=req_id,
                symbol=contract.symbol,
                local_symbol=contract.local_symbol,
                observable_name=observable_name,
            )

            return (False, req_id)

    def get_contract_info(self, req_id: int) -> Tuple[str, str]:
        """
        Get contract info for a request.

        Args:
            req_id: Request ID

        Returns:
            Tuple of (symbol, local_symbol)
        """
        with self._lock:
            if req_id in self._requests:
                req = self._requests[req_id]
                return (req.symbol, req.local_symbol)
            return ("", "")

    def remove_request(self, req_id: int) -> None:
        """
        Remove a request and all associated data.

        Args:
            req_id: Request ID
        """
        with self._lock:
            if req_id in self._requests:
                req = self._requests[req_id]
                key = (req.symbol, req.local_symbol, req.observable_name)
                self._contract_map.pop(key, None)
                del self._requests[req_id]

            self._callbacks.pop(req_id, None)
            self._temp_data.pop(req_id, None)

    # ----------------------------------------------------------------
    # Temporary Data (for accumulating results like historical bars)
    # ----------------------------------------------------------------

    def init_temp_data(self, req_id: int) -> None:
        """
        Initialize temporary data storage for a request.

        Args:
            req_id: Request ID
        """
        with self._lock:
            self._temp_data[req_id] = []

    def add_temp_data(self, req_id: int, data: Any) -> None:
        """
        Add data to temporary storage.

        Args:
            req_id: Request ID
            data: Data to add
        """
        with self._lock:
            if req_id in self._temp_data:
                self._temp_data[req_id].append(data)

    def get_temp_data(self, req_id: int) -> List[Any]:
        """
        Get accumulated temporary data.

        Args:
            req_id: Request ID

        Returns:
            List of accumulated data
        """
        with self._lock:
            return self._temp_data.get(req_id, [])

    def clear_temp_data(self, req_id: int) -> None:
        """
        Clear temporary data for a request.

        Args:
            req_id: Request ID
        """
        with self._lock:
            self._temp_data.pop(req_id, None)

    # ----------------------------------------------------------------
    # Debug/Logging
    # ----------------------------------------------------------------

    def log_state(self) -> None:
        """Log current state for debugging."""
        with self._lock:
            log.debug(f"IBState: {len(self._requests)} active requests")
            for req_id, req in self._requests.items():
                log.debug(
                    f"  {req_id}: {req.symbol}/{req.local_symbol} "
                    f"({req.observable_name})"
                )
