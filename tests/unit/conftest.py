"""
Pytest configuration and fixtures
"""
import pytest
import sys
from unittest.mock import Mock, MagicMock

# Mock all external dependencies before any imports
@pytest.fixture(scope="session", autouse=True)
def mock_dependencies():
    """Mock external dependencies for tests"""
    # Mock database dependencies
    sys.modules['psycopg2'] = Mock()
    sys.modules['psycopg2.pool'] = Mock()
    sys.modules['psycopg2.extras'] = Mock()
    
    # Mock LLM helpers
    sys.modules['src.utils.llm_helper'] = Mock()
    sys.modules['src.utils.openrouter_helper'] = Mock()
    sys.modules['src.utils.gemini_helper'] = Mock()
    sys.modules['src.utils.llm_factory'] = Mock()
    
    # Mock postgres pool
    mock_pool = Mock()
    mock_pool.get_postgres_connection = Mock(return_value=None)
    mock_pool.return_connection = Mock()
    sys.modules['src.utils.postgres_pool'] = mock_pool
    
    yield
    
    # Cleanup if needed
    pass

