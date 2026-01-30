import os
from typing import Optional
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader, APIKey

# Header name clients must send: X-API-Key: <secret>
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def require_api_key(api_key: str = Security(api_key_header)) -> APIKey:
    server_key: Optional[str] = os.getenv("API_KEY")
    
    if not server_key:
        # Misconfiguration on server side
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server API key not configured",
        )
    if not api_key or api_key != server_key:
        # Unauthorized
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "API key"},
        )
    
    return api_key


