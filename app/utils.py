"""Utility functions for the bot."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Get current UTC time (Python 3.12+ compatible).
    
    Replaces deprecated utc_now().
    
    Returns:
        Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)
