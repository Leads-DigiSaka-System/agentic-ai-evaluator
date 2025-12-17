"""
Cooperative context dependency for extracting cooperative from headers
"""
from fastapi import Header, HTTPException, status
from typing import Optional

async def get_cooperative(
    x_cooperative: Optional[str] = Header(None, alias="X-Cooperative")
) -> str:
    """
    Extract cooperative from X-Cooperative header
    
    This dependency extracts the cooperative identifier from the X-Cooperative header
    and validates it. All endpoints that need cooperative-specific access should
    use this dependency.
    
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
    """
    if not x_cooperative:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Cooperative header is required for cooperative-specific access"
        )
    
    # Validate cooperative is not empty
    cooperative = x_cooperative.strip()
    if len(cooperative) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Cooperative header cannot be empty"
        )
    
    return cooperative

