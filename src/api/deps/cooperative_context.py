"""
Cooperative context dependency for extracting cooperative from headers
"""
from fastapi import Header, HTTPException, status
from typing import Optional

from src.shared.validation import validate_header_value


async def get_cooperative(
    x_cooperative: Optional[str] = Header(None, alias="X-Cooperative")
) -> str:
    """
    Extract cooperative from X-Cooperative header
    
    This dependency extracts the cooperative identifier from the X-Cooperative header
    and validates it (max 200 chars). All endpoints that need cooperative-specific access
    should use this dependency.
    
    Usage:
        @router.post("/agent")
        async def upload_file(
            cooperative: str = Depends(get_cooperative),
            user_id: str = Depends(get_user_id),
            file: UploadFile = File(...)
        ):
            # Use cooperative for access control
            pass
    
    Raises:
        HTTPException: If X-Cooperative header is missing or empty
        ValidationError: If header value exceeds max length (400, handled globally)
    """
    if not x_cooperative:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Cooperative header is required for cooperative-specific access"
        )
    return validate_header_value(x_cooperative, "X-Cooperative", max_length=200)

