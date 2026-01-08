"""
Simple test to verify pytest is working
"""
import pytest
import re


def test_pytest_works():
    """Simple test to verify pytest is working"""
    assert 1 + 1 == 2


def test_regex_pattern():
    """Test regex pattern used in _clean_agent_response"""
    # Test markdown header removal
    text = "## Search Results\n\nContent"
    cleaned = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    assert "##" not in cleaned
    assert "Search Results" in cleaned


def test_string_operations():
    """Test basic string operations"""
    text = "   test   "
    assert text.strip() == "test"
    
    text = "None"
    assert text.lower() == "none"

