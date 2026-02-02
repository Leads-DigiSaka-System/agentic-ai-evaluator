# src/api/reports.py
from fastapi import APIRouter, Depends, Request
from src.infrastructure.vector_store.list_reports import report_lister
from src.api.deps.cooperative_context import get_cooperative
from src.shared.limiter_config import limiter

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/list")
@limiter.limit("60/minute")
async def list_all_reports(
    request: Request,
    cooperative: str = Depends(get_cooperative),
):
    """
    List reports filtered by cooperative only.
    Same cooperative can see all data within that cooperative.
    """
    return await report_lister.list_all_reports(cooperative=cooperative)

@router.get("/stats")
@limiter.limit("60/minute")
async def get_stats(
    request: Request,
    cooperative: str = Depends(get_cooperative),
):
    """Get collection statistics filtered by cooperative only"""
    return report_lister.get_collection_stats(cooperative=cooperative)