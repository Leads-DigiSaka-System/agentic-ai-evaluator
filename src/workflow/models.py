"""
Data models for workflow operations.

This module contains Pydantic models and TypedDict definitions
for complex function parameters to improve type safety and reduce
parameter list length.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SimpleStorageApprovalRequest(BaseModel):
    """Model for simple storage approval requests"""
    cache_id: str
    approved: bool


class ReportPayload(BaseModel):
    """Model for report payload preparation"""
    report: Dict[str, Any]
    analysis: Dict[str, Any]
    graph_suggestions: Dict[str, Any]
    basic_info: Dict[str, Any]
    calculated: Dict[str, Any]
    performance: Dict[str, Any]
    cooperator_feedback: Dict[str, Any]
    form_id: str
    full_response: Dict[str, Any]
    summary_text: str


class StorageRequest(BaseModel):
    """Model for storage approval requests"""
    cache_id: str
    approved: bool
    session_id: Optional[str] = None


class WorkflowMetrics(BaseModel):
    """Model for workflow metrics logging"""
    success: bool
    error_count: int
    chunk_count: int
    chart_count: int
    form_type: str
    is_valid_content: bool
    final_step: str
    evaluation_confidence: float = 0.5
    data_quality_score: float = 0.0


class ReportResponse(BaseModel):
    """Model for standardized report response"""
    report_number: int
    file_name: str
    form_id: str = ""
    form_type: str = ""
    extracted_content: str = ""
    analysis: Dict[str, Any] = Field(default_factory=dict)
    graph_suggestions: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    processing_metrics: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)
    storage_status: str = "ready_for_approval"
    storage_message: str = "Analysis completed. Use /api/storage/preview to review and /api/storage/approve to store."
