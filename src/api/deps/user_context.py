"""
User context dependency for extracting user_id from headers
"""
from fastapi import Header, HTTPException, status
from typing import Optional

from src.shared.validation import validate_header_value


async def get_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-ID")
) -> str:
    """
    Extract user_id from X-User-ID header
    
    This dependency extracts the user_id from the X-User-ID header
    and validates it (max 200 chars). All endpoints that need user isolation
    should use this dependency.
    
    Usage:
        @router.post("/agent")
        async def upload_file(
            user_id: str = Depends(get_user_id),
            file: UploadFile = File(...)
        ):
            # Use user_id for data isolation
            pass
    
    Raises:
        HTTPException: If X-User-ID header is missing or empty
        ValidationError: If header value exceeds max length (400, handled globally)
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-ID header is required for user data isolation"
        )
    return validate_header_value(x_user_id, "X-User-ID", max_length=200)

