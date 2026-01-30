"""
Pytest configuration and fixtures
"""
import sys
from pathlib import Path

# Ensure project root is on path so "src" is importable (e.g. uv run pytest)
_root = Path(__file__).resolve().parent.parent.parent
_root_str = str(_root)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

# Install mocks at conftest load time so any later import (e.g. langfuse, arq) sees them
def _install_mocks():
    from unittest.mock import Mock, MagicMock

    # Mock database dependencies
    sys.modules.setdefault('psycopg2', Mock())
    sys.modules.setdefault('psycopg2.pool', Mock())
    sys.modules.setdefault('psycopg2.extras', Mock())

    # Mock arq so progress.py / redis_pool / cache can be imported
    if 'arq' not in sys.modules or getattr(sys.modules['arq'], '__name__', '') == 'unittest.mock.MagicMock':
        _arq = MagicMock()
        _arq.connections = MagicMock()
        _arq.connections.RedisSettings = MagicMock()
        _arq.create_pool = MagicMock()
        sys.modules['arq'] = _arq
        sys.modules['arq.connections'] = _arq.connections

    # Mock langfuse so "from langfuse import get_client, observe" works
    if 'langfuse' not in sys.modules or not hasattr(sys.modules['langfuse'], 'get_client'):
        _langfuse = MagicMock()
        _langfuse.get_client = MagicMock(return_value=MagicMock())
        _langfuse.observe = MagicMock(return_value=lambda f: f)
        _langfuse.Langfuse = MagicMock()
        _ctx = MagicMock()
        _ctx.__enter__ = MagicMock(return_value=None)
        _ctx.__exit__ = MagicMock(return_value=False)
        _langfuse.propagate_attributes = MagicMock(return_value=_ctx)
        sys.modules['langfuse'] = _langfuse
        _lf_lc = MagicMock()
        _lf_lc.CallbackHandler = MagicMock(return_value=MagicMock())
        sys.modules['langfuse.langchain'] = _lf_lc

    # Mock langchain_google_genai so src.shared.llm_helper can be imported
    sys.modules.setdefault('langchain_google_genai', MagicMock())

    # Mock LLM helpers (legacy paths)
    sys.modules.setdefault('src.utils.llm_helper', Mock())
    sys.modules.setdefault('src.utils.openrouter_helper', Mock())
    sys.modules.setdefault('src.utils.gemini_helper', Mock())
    sys.modules.setdefault('src.utils.llm_factory', Mock())

    # Mock postgres pool
    if 'src.utils.postgres_pool' not in sys.modules:
        mock_pool = Mock()
        mock_pool.get_postgres_connection = Mock(return_value=None)
        mock_pool.return_connection = Mock()
        sys.modules['src.utils.postgres_pool'] = mock_pool

_install_mocks()

import pytest
from unittest.mock import Mock, MagicMock


@pytest.fixture(scope="session", autouse=True)
def mock_dependencies():
    """Re-apply mocks for tests that need them."""
    _install_mocks()
    yield

