"""
Unit tests for rate limiting configuration.

Tests limiter_config (Limiter instance, key_func) and RATE_LIMIT_ENABLED in config.
"""
import pytest


class TestLimiterConfig:
    """Tests for src.shared.limiter_config."""

    def test_limiter_is_limiter_instance(self):
        from slowapi import Limiter
        from src.shared.limiter_config import limiter
        assert isinstance(limiter, Limiter)

    def test_limiter_uses_get_remote_address(self):
        from slowapi.util import get_remote_address
        from src.shared.limiter_config import limiter
        assert limiter._key_func is get_remote_address


class TestRateLimitEnabledConfig:
    """Tests for RATE_LIMIT_ENABLED in src.core.config."""

    def test_rate_limit_enabled_is_bool(self):
        from src.core.config import RATE_LIMIT_ENABLED
        assert isinstance(RATE_LIMIT_ENABLED, bool)

    def test_rate_limit_enabled_defined_in_config(self):
        import src.core.config as config
        assert hasattr(config, "RATE_LIMIT_ENABLED")
