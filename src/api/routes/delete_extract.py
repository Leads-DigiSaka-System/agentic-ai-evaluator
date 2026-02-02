# delete_endpoint.py
from fastapi import APIRouter, HTTPException, Query, Request
from src.infrastructure.vector_store.delete import delete_from_qdrant, delete_all_from_collection
from src.shared.limiter_config import limiter
from src.shared.validation import validate_id

router = APIRouter()


@router.delete("/delete/{form_id}")
@limiter.limit("10/minute")
async def delete_form(request: Request, form_id: str):
    """
    Delete a single demo trial record from Qdrant using its form_id.
    
    ⚠️ ADMIN ONLY: This endpoint is for admin use only.
    
    Example: DELETE /delete/LA-2025-0007
    
    Args:
        form_id: Unique identifier for the form to delete
        
    Returns:
        dict: Status and details of the deletion operation
    """
    form_id = validate_id(form_id, name="form_id")
    # Admin-only operation - no user_id filtering needed
    result = delete_from_qdrant(form_id)
    
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result


@router.delete("/delete-all/{collection_name}")
@limiter.limit("5/minute")
async def delete_all_forms(
    request: Request,
    collection_name: str,
    confirm: bool = Query(False, description="Must be set to true to confirm deletion"),
):
    """
    ⚠️ DANGER: Delete ALL records from a Qdrant collection.
    
    This is a DESTRUCTIVE operation that cannot be undone!
    
    Example: DELETE /delete-all/demo_forms?confirm=true
    
    Args:
        collection_name: Name of the collection to clear
        confirm: Safety flag - must be set to true to proceed
        
    Returns:
        dict: Status and details of the deletion operation
        
    Raises:
        HTTPException: If confirm is not true or operation fails
    """
    # Safety check: Require explicit confirmation
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion not confirmed. Add '?confirm=true' to the URL to proceed. "
                   "WARNING: This will delete ALL records in the collection!"
        )

    collection_name = validate_id(collection_name, name="collection_name")
    # Perform deletion
    result = delete_all_from_collection(collection_name)
    
    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    
    return result