"""
API Key authentication for FastAPI.
Supports multiple API keys (API_KEYS) and optional development bypass when no keys are set.
"""
import logging
from typing import Optional

from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

from src.core.config import API_KEYS, ENVIRONMENT

logger = logging.getLogger(__name__)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def require_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    if not API_KEYS:
        if ENVIRONMENT == "development":
            logger.warning("API key validation disabled in development (no API keys configured)")
            return "development-bypass"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured",
            headers={"WWW-Authenticate": "API key"},
        )

    if not api_key or not api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )

    key = api_key.strip()
    if key not in API_KEYS:
        logger.warning(f"Invalid API key attempted: {key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )
    return key
