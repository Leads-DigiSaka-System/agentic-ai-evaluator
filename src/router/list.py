# src/api/reports.py
from fastapi import APIRouter
from src.database.list_reports import report_lister

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("/list")
async def list_all_reports():
    """
    List ALL reports - Simple get all, no pagination.
    All users can see all reports (no filtering).
    """
    return await report_lister.list_all_reports()

@router.get("/stats")
async def get_stats():
    """Get collection statistics"""
    return report_lister.get_collection_stats()