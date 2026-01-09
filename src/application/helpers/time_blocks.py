"""
Time block calculation utilities for historical data downloads.
"""

from datetime import datetime, timedelta
from typing import List, Tuple


def get_time_blocks(
    start: datetime,
    end: datetime,
    block_size_days: int = 365,
) -> List[Tuple[datetime, datetime]]:
    """
    Split a date range into blocks of a maximum size.

    Used for downloading historical data in manageable chunks.

    Args:
        start: Start datetime
        end: End datetime
        block_size_days: Maximum block size in days

    Returns:
        List of (start, end) datetime tuples

    Example:
        blocks = get_time_blocks(
            datetime(2020, 1, 1),
            datetime(2023, 1, 1),
            block_size_days=365
        )
        # Returns 3 blocks of ~365 days each
    """
    diff_days = (end - start).days

    if diff_days <= block_size_days:
        return [(start, end)]

    result = []
    current = start
    step = timedelta(days=block_size_days)

    while current < end:
        block_start = current
        current += step
        block_end = min(current, end)
        result.append((block_start, block_end))

    return result
