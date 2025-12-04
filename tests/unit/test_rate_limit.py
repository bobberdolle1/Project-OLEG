"""Tests for rate limiting."""

import pytest
import time

from app.middleware.rate_limit import RateLimiter


def test_rate_limiter_allows_requests_within_limit():
    """Test that rate limiter allows requests within limit."""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    user_id = 12345
    
    assert limiter.is_allowed(user_id) is True
    assert limiter.is_allowed(user_id) is True
    assert limiter.is_allowed(user_id) is True


def test_rate_limiter_blocks_requests_over_limit():
    """Test that rate limiter blocks requests over limit."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    user_id = 12345
    
    assert limiter.is_allowed(user_id) is True
    assert limiter.is_allowed(user_id) is True
    assert limiter.is_allowed(user_id) is False


def test_rate_limiter_resets_after_window():
    """Test that rate limiter resets after time window."""
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    user_id = 12345
    
    assert limiter.is_allowed(user_id) is True
    assert limiter.is_allowed(user_id) is True
    assert limiter.is_allowed(user_id) is False
    
    # Wait for window to expire
    time.sleep(1.1)
    
    assert limiter.is_allowed(user_id) is True


def test_rate_limiter_different_users():
    """Test that rate limiter tracks users separately."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    user1 = 12345
    user2 = 67890
    
    assert limiter.is_allowed(user1) is True
    assert limiter.is_allowed(user1) is True
    assert limiter.is_allowed(user1) is False
    
    # User 2 should still be allowed
    assert limiter.is_allowed(user2) is True
    assert limiter.is_allowed(user2) is True


def test_rate_limiter_remaining_time():
    """Test remaining time calculation."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    user_id = 12345
    
    limiter.is_allowed(user_id)
    limiter.is_allowed(user_id)
    limiter.is_allowed(user_id)  # This should be blocked
    
    remaining = limiter.get_remaining_time(user_id)
    assert 0 < remaining <= 60
