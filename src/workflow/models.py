from pydantic import BaseModel, Field


class SimpleStorageApprovalRequest(BaseModel):
    """Simplified request model for storage approval using cache"""
    cache_id: str = Field(..., description="Cache ID from agent response")
    approved: bool = Field(..., description="User approval for storage")
