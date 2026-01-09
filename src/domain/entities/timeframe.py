"""
Timeframe and Duration enumerations.
"""

from enum import Enum


class TimeFrame(Enum):
    """
    Bar size / timeframe for historical data.

    Values match IB API bar size strings.
    """

    SECOND_1 = "1 secs"
    SECOND_5 = "5 secs"
    SECOND_10 = "10 secs"
    SECOND_15 = "15 secs"
    SECOND_30 = "30 secs"
    MINUTE_1 = "1 min"
    MINUTE_2 = "2 mins"
    MINUTE_3 = "3 mins"
    MINUTE_5 = "5 mins"
    MINUTE_10 = "10 mins"
    MINUTE_15 = "15 mins"
    MINUTE_20 = "20 mins"
    MINUTE_30 = "30 mins"
    HOUR_1 = "1 hour"
    HOUR_2 = "2 hours"
    HOUR_3 = "3 hours"
    HOUR_4 = "4 hours"
    HOUR_8 = "8 hours"
    DAY_1 = "1 day"
    WEEK_1 = "1 week"
    MONTH_1 = "1 month"

    @staticmethod
    def from_str(value: str) -> "TimeFrame":
        """
        Create TimeFrame from string.

        Args:
            value: String value (case-insensitive)

        Returns:
            Corresponding TimeFrame

        Raises:
            ValueError: If value doesn't match any timeframe
        """
        value_lower = value.lower().strip()
        for tf in TimeFrame:
            if tf.value.lower() == value_lower:
                return tf
        raise ValueError(f"Unknown timeframe: {value}")

    @property
    def seconds(self) -> int:
        """Get duration in seconds."""
        mapping = {
            TimeFrame.SECOND_1: 1,
            TimeFrame.SECOND_5: 5,
            TimeFrame.SECOND_10: 10,
            TimeFrame.SECOND_15: 15,
            TimeFrame.SECOND_30: 30,
            TimeFrame.MINUTE_1: 60,
            TimeFrame.MINUTE_2: 120,
            TimeFrame.MINUTE_3: 180,
            TimeFrame.MINUTE_5: 300,
            TimeFrame.MINUTE_10: 600,
            TimeFrame.MINUTE_15: 900,
            TimeFrame.MINUTE_20: 1200,
            TimeFrame.MINUTE_30: 1800,
            TimeFrame.HOUR_1: 3600,
            TimeFrame.HOUR_2: 7200,
            TimeFrame.HOUR_3: 10800,
            TimeFrame.HOUR_4: 14400,
            TimeFrame.HOUR_8: 28800,
            TimeFrame.DAY_1: 86400,
            TimeFrame.WEEK_1: 604800,
            TimeFrame.MONTH_1: 2592000,  # Approximate: 30 days
        }
        return mapping.get(self, 0)

    def __str__(self) -> str:
        return self.value


class Duration(Enum):
    """
    Duration for historical data requests.

    Represents how far back to request data.
    """

    ALL = "All"
    YEARS_20 = "20 Y"
    YEARS_10 = "10 Y"
    YEARS_5 = "5 Y"
    YEARS_2 = "2 Y"
    YEAR_1 = "1 Y"
    MONTHS_6 = "6 M"
    MONTHS_3 = "3 M"
    MONTH_1 = "1 M"
    WEEKS_2 = "2 W"
    WEEK_1 = "1 W"
    DAYS_5 = "5 D"
    DAYS_3 = "3 D"
    DAY_1 = "1 D"

    @staticmethod
    def from_str(value: str) -> "Duration":
        """
        Create Duration from string.

        Args:
            value: String value

        Returns:
            Corresponding Duration

        Raises:
            ValueError: If value doesn't match any duration
        """
        # Handle legacy format
        legacy_mapping = {
            "all": Duration.ALL,
            "20 years": Duration.YEARS_20,
            "10 years": Duration.YEARS_10,
            "5 years": Duration.YEARS_5,
            "1 year": Duration.YEAR_1,
            "1 quarter": Duration.MONTHS_3,
            "1 month": Duration.MONTH_1,
            "1 week": Duration.WEEK_1,
        }

        value_lower = value.lower().strip()
        if value_lower in legacy_mapping:
            return legacy_mapping[value_lower]

        for duration in Duration:
            if duration.value.lower() == value_lower:
                return duration

        raise ValueError(f"Unknown duration: {value}")

    @property
    def days(self) -> int:
        """Get approximate duration in days."""
        mapping = {
            Duration.ALL: 7300,  # ~20 years
            Duration.YEARS_20: 7300,
            Duration.YEARS_10: 3650,
            Duration.YEARS_5: 1825,
            Duration.YEARS_2: 730,
            Duration.YEAR_1: 365,
            Duration.MONTHS_6: 180,
            Duration.MONTHS_3: 90,
            Duration.MONTH_1: 30,
            Duration.WEEKS_2: 14,
            Duration.WEEK_1: 7,
            Duration.DAYS_5: 5,
            Duration.DAYS_3: 3,
            Duration.DAY_1: 1,
        }
        return mapping.get(self, 0)

    def __str__(self) -> str:
        return self.value
