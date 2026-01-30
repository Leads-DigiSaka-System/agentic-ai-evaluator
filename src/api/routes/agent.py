from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from src.ingestion.multiple_handler import MultiReportHandler
from src.core import constants
from src.shared.limiter_config import limiter
from src.core.errors import ProcessingError, ValidationError
from src.shared.logging.clean_logger import get_clean_logger
from src.shared.file_validator import validate_and_raise, FileValidator
from src.services.cache_service import agent_cache
from src.formatter.json_helper import validate_and_clean_agent_response
from src.monitoring.session.langfuse_session_helper import (
    generate_session_id,
    propagate_session_id
)
from src.shared.langfuse_utils import (
    observe_operation,
    safe_get_client as get_langfuse_client,
    flush_langfuse,
    get_trace_url,
    LANGFUSE_AVAILABLE
)
from src.core.config import LANGFUSE_CONFIGURED
from src.api.deps.user_context import get_user_id
from src.api.deps.cooperative_context import get_cooperative
from concurrent.futures import TimeoutError as FutureTimeoutError
from src.infrastructure.redis.redis_pool import get_shared_redis_pool
import uuid
import asyncio

router = APIRouter()
logger = get_clean_logger(__name__)


@router.post("/agent")
@limiter.limit("10/minute")
@observe_operation(name="agent_file_upload")
async def upload_file(
    request: Request, 
    file: UploadFile = File(...), 
    cooperative: str = Depends(get_cooperative),
    user_id: str = Depends(get_user_id),  # ✅ Extract user_id from header
    background: bool = False  # ✅ Query parameter, not form field
):
    """
    Upload and process files
    
    Headers Required:
        X-User-ID: User identifier for data isolation
    
    Args:
        file: File to process
        background: If True, process in background and return job_id
    """
    try:
        logger.info(f"Processing file for user: {user_id}")
        
        # Read file content
        content = await file.read()
        
        # Comprehensive file validation
        validate_and_raise(file.filename, content, field_name="file")
        
        logger.file_upload(file.filename, len(content))
        
        # Generate session ID (include user_id for better tracking)
        session_id = generate_session_id(prefix=f"file_upload_{user_id}")
        logger.info(f"Generated session ID: {session_id} for user: {user_id}")
        
        # Set session_id on trace
        from src.shared.langfuse_utils import safe_update_trace
        safe_update_trace(
            metadata={"file_name": file.filename[:100], "session_id": session_id},
            session_id=session_id
        )
        
        # ✅ Background processing with ARQ
        if background:
            try:
                redis_pool = await get_shared_redis_pool()
                tracking_id = str(uuid.uuid4())
                
                # Get job priority from query params (optional)
                priority = request.query_params.get("priority", "normal")
                from src.core.constants import (
                    ARQ_JOB_PRIORITY_HIGH,
                    ARQ_JOB_PRIORITY_NORMAL,
                    ARQ_JOB_PRIORITY_LOW,
                    REDIS_TRACKING_TTL_SECONDS
                )
                
                # Map priority string to numeric value
                priority_map = {
                    "high": ARQ_JOB_PRIORITY_HIGH,
                    "normal": ARQ_JOB_PRIORITY_NORMAL,
                    "low": ARQ_JOB_PRIORITY_LOW
                }
                job_priority = priority_map.get(priority.lower(), ARQ_JOB_PRIORITY_NORMAL)
                
                # Enqueue job with priority and user_id (ARQ uses _job_id for priority-based ordering)
                job = await redis_pool.enqueue_job(
                    "process_file_background",
                    tracking_id,
                    content,
                    file.filename,
                    session_id,
                    user_id,
                    _job_id=f"{user_id}:{job_priority}-{tracking_id}"  # Include user_id in job_id
                )
                
                # Store tracking_id and user_id mappings
                await redis_pool.setex(
                    f"arq:tracking:{job.job_id}",
                    REDIS_TRACKING_TTL_SECONDS,
                    tracking_id
                )
                await redis_pool.setex(
                    f"arq:user:{job.job_id}",
                    REDIS_TRACKING_TTL_SECONDS,
                    user_id
                )
                
                logger.info(f"Job queued: {job.job_id} (tracking_id: {tracking_id}, user: {user_id}, priority: {priority})")
                
                return {
                    "status": "queued",
                    "job_id": job.job_id,
                    "session_id": session_id,
                    "user_id": user_id,  # ✅ Include in response
                    "priority": priority,
                    "message": "Processing started in background",
                    "progress_url": f"/api/progress/{job.job_id}"
                }
            except Exception as e:
                logger.error(f"Failed to queue job: {e}")
                raise ProcessingError(
                    detail=f"Failed to start background processing: {str(e)}",
                    step="job_queuing",
                    file_name=file.filename[:50]
                )
    
        # ✅ Synchronous processing (keep for backward compatibility)
        # ✅ CRITICAL: Include user_id in propagate_session_id to prevent confusion when multiple users process simultaneously
        try:
            with propagate_session_id(session_id, file_name=file.filename[:100], user_id=user_id):
                result = await asyncio.wait_for(
                    MultiReportHandler.process_multi_report_pdf(content, file.filename, user_id=user_id),
                    timeout=constants.REQUEST_TIMEOUT_SECONDS
                )
                
                logger.file_validation(file.filename, "success", "processed successfully")
                
                # Validate and clean response
                try:
                    cleaned_result = validate_and_clean_agent_response(result)
                    result = cleaned_result
                except Exception as e:
                    logger.warning(f"Failed to clean agent response: {str(e)}")
                
                # Cache result (with user_id for isolation)
                cache_id = None
                try:
                    cache_id = await agent_cache.save_agent_output(result, session_id=session_id, user_id=user_id)
                    logger.cache_save(cache_id, "agent output")
                    
                    # ✅ Add cache_id to result for frontend
                    if isinstance(result, dict):
                        if "reports" in result and isinstance(result["reports"], list) and len(result["reports"]) > 0:
                            # Add to first report
                            result["reports"][0]["cache_id"] = cache_id
                        result["cache_id"] = cache_id
                except Exception as e:
                    logger.warning(f"Failed to cache agent output: {str(e)}")
                
                # Flush Langfuse
                trace_url = get_trace_url()
                if trace_url:
                    logger.info(f"📊 Langfuse trace: {trace_url}")
                flush_langfuse()
                
                return result
                
        except FutureTimeoutError:
            raise ProcessingError(
                detail="File processing timed out",
                step="workflow_execution",
                file_name=file.filename[:50],
                timeout_seconds=constants.REQUEST_TIMEOUT_SECONDS
            )
        
    except (ValidationError, ProcessingError):
        raise
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)[:100]}")
        raise ProcessingError(
            detail=f"Unexpected error during file processing",
            step="file_upload",
            file_name=file.filename[:50] if file.filename else "unknown",
            error=str(e)[:200]
        )