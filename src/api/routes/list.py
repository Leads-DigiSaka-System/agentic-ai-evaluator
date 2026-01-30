# src/api/reports.py
from fastapi import APIRouter, Depends
from src.infrastructure.vector_store.list_reports import report_lister
from src.api.deps.cooperative_context import get_cooperative

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/list")
async def list_all_reports(
    cooperative: str = Depends(get_cooperative)
):
    """
    List reports filtered by cooperative only.
    Same cooperative can see all data within that cooperative.
    """
    return await report_lister.list_all_reports(cooperative=cooperative)

@router.get("/stats")
async def get_stats(
    cooperative: str = Depends(get_cooperative)
):
    """Get collection statistics filtered by cooperative only"""
    return report_lister.get_collection_stats(cooperative=cooperative)