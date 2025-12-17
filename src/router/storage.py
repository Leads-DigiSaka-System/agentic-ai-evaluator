from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from src.services.storage_service import storage_service
from src.services.cache_service import agent_cache
from src.utils.limiter_config import limiter
from src.utils.errors import ProcessingError, ValidationError
from src.utils.clean_logger import get_clean_logger
from src.workflow.models import SimpleStorageApprovalRequest
from src.deps.user_context import get_user_id
from src.deps.cooperative_context import get_cooperative
from src.utils.config import LANGFUSE_CONFIGURED
from datetime import datetime

router = APIRouter()
logger = get_clean_logger(__name__)

# Unified Langfuse utilities - single import point
from src.utils.langfuse_utils import (
    LANGFUSE_AVAILABLE,
    safe_get_client as get_client,
    safe_observe
)
import functools
import inspect

# Wrapper to preserve function signature for slowapi compatibility
def observe_with_signature_preservation(*args, **kwargs):
    """Wrapper for @observe that preserves function signature for slowapi"""
    def decorator(func):
        # Apply observe decorator
        observed_func = safe_observe(*args, **kwargs)(func)
        # Preserve original function signature metadata and attributes
        functools.update_wrapper(observed_func, func)
        # Preserve __signature__ for slowapi inspection
        if hasattr(func, '__signature__'):
            observed_func.__signature__ = func.__signature__
        else:
            try:
                observed_func.__signature__ = inspect.signature(func)
            except (ValueError, TypeError):
                pass
        return observed_func
    return decorator


@router.post("/storage/approve-simple")
@limiter.limit("10/minute")
@observe_with_signature_preservation(name="approve_storage_simple")
async def approve_storage_simple(
    request: Request, 
    approval_request: SimpleStorageApprovalRequest,
    user_id: str = Depends(get_user_id),
    cooperative: str = Depends(get_cooperative)  # ✅ Extract user_id from header
):
    """
    Simplified storage approval using cached agent output with user isolation
    
    Headers Required:
        X-User-ID: User identifier (must match cache owner)
    
    This endpoint automatically retrieves cached agent output and stores it.
    Frontend only needs to provide cache_id and approval decision.
    
    Args:
        cache_id: Cache ID from agent response
        approved: True to store, False to reject storage
        
    Returns:
        Storage results with success/failure status
    """
    try:
        logger.cache_retrieve(approval_request.cache_id, "processing")
        logger.info(f"User {user_id} approval: {approval_request.approved}")
        
        # Update trace with approval metadata and tags
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    # Add tags to trace
                    client.update_current_trace(
                        tags=["storage", "approval", "api"]
                    )
                    client.update_current_observation(
                        metadata={
                            "cache_id": approval_request.cache_id[:50],
                            "approved": approval_request.approved,
                            "storage_type": "simple_approval",
                            "user_id": user_id,
                            "cooperative": cooperative
                        }
                    )
            except Exception as e:
                logger.debug(f"Could not update observation: {e}")
        
        # Get cached agent output (with user_id for isolation)
        cached_data = await agent_cache.get_cached_output(approval_request.cache_id, user_id=user_id)
        
        if not cached_data:
            raise ProcessingError(
                detail="Cached agent output not found or expired",
                step="cache_retrieval",
                file_name="cached_output"
            )
        
        # ✅ Verify cache belongs to user
        cached_user_id = cached_data.get("user_id")
        if cached_user_id and cached_user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail="Cache does not belong to this user"
            )
        
        # Get the actual cached output (agent_response)
        cached_output = cached_data.get("agent_response", cached_data) if isinstance(cached_data, dict) else cached_data
        
        # Retrieve session_id from cache to link storage approval to original session
        original_session_id = None
        if isinstance(cached_data, dict):
            # Check if session_id is stored directly in cache_data (we store it there)
            original_session_id = cached_data.get("session_id")
        
        # Check if storage is ready
        reports = cached_output.get("reports", [])
        if not reports:
            raise ProcessingError(
                detail="No reports found in cached output",
                step="cache_validation",
                file_name="cached_output"
            )
        
        first_report = reports[0]
        storage_status = first_report.get("storage_status")
        
        if storage_status != "ready_for_approval":
            raise ProcessingError(
                detail=f"Storage not ready: {storage_status}",
                step="storage_validation",
                file_name=first_report.get("file_name", "unknown")
            )
        
        # Link storage approval to original session if session_id is available
        # This will group storage approval trace with the original file upload session
        if LANGFUSE_AVAILABLE and original_session_id:
            try:
                from src.monitoring.session.langfuse_session_helper import propagate_session_id
                from src.monitoring.trace.langfuse_helper import get_langfuse_client
                from src.utils.config import LANGFUSE_CONFIGURED
                
                if LANGFUSE_CONFIGURED:
                    client = get_langfuse_client()
                    if client:
                        # Set session_id on trace to link to original session
                        client.update_current_trace(
                            session_id=original_session_id,
                            metadata={
                                "linked_to_original_session": True,
                                "original_session_id": original_session_id,
                                "cache_id": approval_request.cache_id[:50]
                            }
                        )
                        logger.info(f"Storage approval linked to session: {original_session_id}")
            except Exception as e:
                logger.debug(f"Could not link to original session: {e}")
        
        # Handle rejection
        if not approval_request.approved:
            logger.info(f"Storage rejected by user for cache: {approval_request.cache_id[:8]}...")
            
            # Update trace with rejection - make it clear in the trace
            if LANGFUSE_AVAILABLE:
                try:
                    from src.monitoring.scores.storage_score import log_storage_rejection_scores
                    
                    client = get_client()
                    if client:
                        # Update trace with rejection tags and metadata
                        client.update_current_trace(
                            tags=["storage", "approval", "api", "rejected"],
                            metadata={
                                "status": "rejected",
                                "reason": "user_rejection",
                                "cache_id": approval_request.cache_id[:50],
                                "approved": False
                            }
                        )
                        # Update observation with rejection details
                        client.update_current_observation(
                            metadata={
                                "status": "rejected",
                                "reason": "user_rejection",
                                "action": "cache_deleted",
                                "approved": False
                            }
                        )
                        
                        # Log rejection scores using dedicated score module
                        log_storage_rejection_scores()
                except Exception as e:
                    logger.debug(f"Could not update observation: {e}")
            
            # Clean up cache (with user_id validation for security)
            await agent_cache.delete_cache(approval_request.cache_id, user_id=user_id)
            
            return {
                "status": "rejected",
                "message": "Storage rejected by user",
                "cache_id": approval_request.cache_id,
                "timestamp": datetime.now().isoformat()
            }
        
        # Process storage for single or multiple reports
        # Wrap in propagate_session_id context to ensure all child operations inherit session_id
        if original_session_id and LANGFUSE_AVAILABLE:
            try:
                from src.monitoring.session.langfuse_session_helper import propagate_session_id
                from src.utils.config import LANGFUSE_CONFIGURED
                
                if LANGFUSE_CONFIGURED:
                    # Process storage within session context
                    with propagate_session_id(original_session_id, cache_id=approval_request.cache_id[:50], user_id=user_id):
                        if len(reports) == 1:
                            # Single report
                            result = await _process_single_report_storage(first_report, user_id=user_id, cooperative=cooperative)
                        else:
                            # Multiple reports - use batch storage
                            result = await _process_multiple_reports_storage(reports, user_id=user_id, cooperative=cooperative)
                else:
                    # Fallback if Langfuse not configured
                    if len(reports) == 1:
                        result = await _process_single_report_storage(first_report, user_id=user_id, cooperative=cooperative)
                    else:
                        result = await _process_multiple_reports_storage(reports, user_id=user_id, cooperative=cooperative)
            except Exception as e:
                logger.debug(f"Could not propagate session_id in storage: {e}")
                # Fallback to normal processing
                if len(reports) == 1:
                    result = await _process_single_report_storage(first_report, user_id=user_id, cooperative=cooperative)
                else:
                    result = await _process_multiple_reports_storage(reports, user_id=user_id, cooperative=cooperative)
        else:
            # No session_id available, process normally
            if len(reports) == 1:
                # Single report
                result = await _process_single_report_storage(first_report, user_id=user_id, cooperative=cooperative)
            else:
                # Multiple reports - use batch storage
                result = await _process_multiple_reports_storage(reports, user_id=user_id, cooperative=cooperative)
        
        # Update trace with storage results, tags, and scores
        if LANGFUSE_AVAILABLE:
            try:
                from src.monitoring.scores.storage_score import log_storage_scores
                
                client = get_client()
                if client:
                    storage_type = "single" if len(reports) == 1 else "batch"
                    storage_status = result.get("status", "unknown")
                    
                    # Update trace with tags
                    client.update_current_trace(
                        tags=["storage", "approval", "api", storage_type, storage_status]
                    )
                    
                    # Log scores using dedicated score module
                    log_storage_scores(reports, cached_output, result, storage_type)
                    
                    # Update metadata
                    metadata = {
                        "status": storage_status,
                        "reports_count": len(reports),
                        "storage_type": storage_type
                    }
                    if "successful_items" in result:
                        metadata["successful_items"] = result.get("successful_items")
                        metadata["failed_items"] = result.get("failed_items")
                    client.update_current_observation(metadata=metadata)
            except Exception as e:
                logger.debug(f"Could not update observation: {e}")
        
        # Clean up cache after successful storage (with user_id validation for security)
        if result.get("status") == "success":
            await agent_cache.delete_cache(approval_request.cache_id, user_id=user_id)
            logger.cache_delete(approval_request.cache_id)
        
        return result
        
    except (ValidationError, ProcessingError):
        # Re-raise custom errors as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error during simple storage approval: {str(e)[:100]}")
        
        # Update trace with error
        if LANGFUSE_AVAILABLE:
            try:
                from src.monitoring.trace.langfuse_helper import update_trace_with_error
                update_trace_with_error(e, {
                    "step": "simple_storage_approval",
                    "cache_id": approval_request.cache_id[:50]
                })
            except Exception as langfuse_err:
                logger.debug(f"Failed to log error to Langfuse: {langfuse_err}")
        
        raise ProcessingError(
            detail="Unexpected error during simple storage approval",
            step="simple_storage_approval",
            error=str(e)[:200]
        )


async def _process_single_report_storage(report_data: Dict[str, Any], user_id: str = None, cooperative: str = None) -> Dict[str, Any]:
    """Process storage for single report
    
    Args:
        report_data: Report data from cache
        user_id: User ID from frontend header (source of truth) - NOT from cached data
        cooperative: Cooperative ID from frontend header (source of truth) - NOT from cached data
    """
    try:
        # Convert to state format
        # ✅ Use user_id from frontend header (source of truth), NOT from cached report_data
        state_data = {
            "file_name": report_data["file_name"],
            "form_type": report_data.get("form_type"),
            "analysis_result": report_data.get("analysis", {}),
            "graph_suggestions": report_data.get("graph_suggestions", {}),
            "extracted_markdown": report_data.get("extracted_content", ""),
            "chunks": report_data.get("chunks", []),
            "errors": report_data.get("errors", []),
            "file_validation": report_data.get("validation", {}).get("file_validation"),
            "is_valid_content": report_data.get("validation", {}).get("content_validation", {}).get("is_valid_demo", False),
            "content_validation": report_data.get("validation", {}).get("content_validation"),
            "current_step": "simple_storage_approval",
            "_user_id": user_id,  # ✅ Use user_id from frontend header (source of truth)
            "_cooperative": cooperative  # ✅ Use cooperative from frontend header (source of truth)
        }
        
        # Prepare and store
        storage_data = storage_service.prepare_storage_data(state_data)
        storage_result = storage_service.store_all(storage_data)
        
        if storage_result["success"]:
            logger.storage_success("single report", 1, report_data['file_name'][:50])
        else:
            logger.storage_error("single report", report_data['file_name'][:50])
        
        return {
            "status": "success" if storage_result["success"] else "failed",
            "storage_result": storage_result,
            "message": "Storage completed successfully" if storage_result["success"] else "Storage failed"
        }
        
    except Exception as e:
        logger.error(f"Single report storage processing failed: {str(e)}")
        return {
            "status": "failed",
            "message": f"Storage processing failed: {str(e)}"
        }


async def _process_multiple_reports_storage(reports: List[Dict[str, Any]], user_id: str = None, cooperative: str = None) -> Dict[str, Any]:
    """Process batch storage for multiple reports
    
    Args:
        reports: List of report data from cache
        user_id: User ID from frontend header (source of truth) - NOT from cached data
        cooperative: Cooperative ID from frontend header (source of truth) - NOT from cached data
    """
    try:
        results = []
        success_count = 0
        
        for i, report in enumerate(reports):
            try:
                # Convert to state format
                # ✅ Use user_id from frontend header (source of truth), NOT from cached report
                state_data = {
                    "file_name": report["file_name"],
                    "form_type": report.get("form_type"),
                    "analysis_result": report.get("analysis", {}),
                    "graph_suggestions": report.get("graph_suggestions", {}),
                    "extracted_markdown": report.get("extracted_content", ""),
                    "chunks": report.get("chunks", []),
                    "errors": report.get("errors", []),
                    "file_validation": report.get("validation", {}).get("file_validation"),
                    "is_valid_content": report.get("validation", {}).get("content_validation", {}).get("is_valid_demo", False),
                    "content_validation": report.get("validation", {}).get("content_validation"),
                    "current_step": "batch_storage_approval",
                    "_user_id": user_id,  # ✅ Use user_id from frontend header (source of truth)
                    "_cooperative": cooperative  # ✅ Use cooperative from frontend header (source of truth)
                }
                
                # Prepare and store
                storage_data = storage_service.prepare_storage_data(state_data)
                storage_result = storage_service.store_all(storage_data)
                
                results.append({
                    "index": i,
                    "file_name": report["file_name"],
                    "status": "success" if storage_result["success"] else "failed",
                    "form_id": storage_result.get("form_id"),
                    "storage_result": storage_result
                })
                
                if storage_result["success"]:
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing batch item {i}: {str(e)[:100]}")
                results.append({
                    "index": i,
                    "file_name": report["file_name"],
                    "status": "error",
                    "error": str(e)[:200]
                })
        
        logger.storage_success("batch storage", success_count, f"{len(reports)} reports")
        
        return {
            "status": "completed",
            "total_items": len(reports),
            "successful_items": success_count,
            "failed_items": len(reports) - success_count,
            "results": results,
            "message": f"Batch storage completed: {success_count}/{len(reports)} successful"
        }
        
    except Exception as e:
        logger.storage_error("batch storage", str(e))
        return {
            "status": "failed",
            "message": f"Batch storage processing failed: {str(e)}"
        }