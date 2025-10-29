"""
Custom Error Handler for Better Error Responses
"""

from fastapi import HTTPException
from datetime import datetime
from typing import Any, Dict, Optional


class ContextualHTTPException(HTTPException):
    """
    Enhanced HTTPException with context for better debugging
    
    Usage:
        raise ContextualHTTPException(
            status_code=500,
            detail="File processing failed",
            context={
                "file_name": "demo.pdf",
                "step": "extraction",
                "file_size": 1024000,
                "operation": "pdf_text_extraction"
            }
        )
    """
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        # Build enhanced error detail
        error_detail = {
            "error": detail,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        if context:
            error_detail["context"] = context
        
        super().__init__(status_code=status_code, detail=error_detail)


class ValidationError(ContextualHTTPException):
    """Error for validation failures"""
    
    def __init__(self, detail: str, field: Optional[str] = None, value: Any = None):
        context = {}
        if field:
            context["field"] = field
        if value is not None:
            context["value"] = str(value)[:100]  # Limit value length
        
        super().__init__(
            status_code=400,
            detail=detail,
            context=context,
            error_type="validation_error"
        )


class ProcessingError(ContextualHTTPException):
    """Error for processing failures"""
    
    def __init__(self, detail: str, step: str, **context):
        super().__init__(
            status_code=500,
            detail=detail,
            context={"step": step, **context},
            error_type="processing_error"
        )


class TimeoutError(ContextualHTTPException):
    """Error for timeout failures"""
    
    def __init__(self, detail: str, timeout_seconds: float, operation: str):
        super().__init__(
            status_code=504,
            detail=detail,
            context={
                "timeout_seconds": timeout_seconds,
                "operation": operation
            },
            error_type="timeout_error"
        )

