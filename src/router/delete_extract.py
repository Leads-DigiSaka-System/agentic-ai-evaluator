# delete_endpoint.py
from fastapi import APIRouter
from src.database.delete import delete_from_qdrant

router = APIRouter()

@router.delete("/delete/{form_id}")
async def delete_form(form_id: str):
    """
    Delete a demo trial record from Qdrant using its form_id.
    Example: DELETE /delete/LA-2025-0007
    """
    result = delete_from_qdrant(form_id)
    return result
