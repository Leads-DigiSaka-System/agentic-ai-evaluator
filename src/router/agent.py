from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from src.Upload.multiple_handler import MultiReportHandler
from src.utils import constants
from src.utils.limiter_config import limiter
from src.utils.config import REDIS_URL
from src.utils.errors import ProcessingError, ValidationError
from src.utils.clean_logger import get_clean_logger
from src.utils.file_validator import validate_and_raise, FileValidator
from src.services.cache_service import agent_cache
from src.formatter.json_helper import validate_and_clean_agent_response
from src.monitoring.session.langfuse_session_helper import (
    generate_session_id,
    propagate_session_id
)
from src.monitoring.trace.langfuse_helper import (
    observe_operation,
    get_langfuse_client,
    LANGFUSE_CONFIGURED,
    flush_langfuse,
    get_trace_url
)
from concurrent.futures import TimeoutError as FutureTimeoutError
from arq import create_pool
from arq.connections import RedisSettings
import uuid
import asyncio

router = APIRouter()
logger = get_clean_logger(__name__)


@router.post("/agent")
@limiter.limit("10/minute")
@observe_operation(name="agent_file_upload")
async def upload_file(request: Request, file: UploadFile = File(...), background: bool = False):
    """
    Upload and process files
    
    Args:
        background: If True, process in background and return job_id
    """
    try:
        # Read file content
        content = await file.read()
        
        # Comprehensive file validation
        validate_and_raise(file.filename, content, field_name="file")
        
        logger.file_upload(file.filename, len(content))
        
        # Generate session ID
        session_id = generate_session_id(prefix="file_upload")
        logger.info(f"Generated session ID: {session_id}")
        
        # Set session_id on trace
        if LANGFUSE_CONFIGURED:
            try:
                client = get_langfuse_client()
                if client:
                    client.update_current_trace(
                        session_id=session_id,
                        metadata={"file_name": file.filename[:100], "session_id": session_id}
                    )
            except Exception as e:
                logger.warning(f"Failed to set session_id on trace: {e}")
        
        # ============================================
        # NEW: Background processing with ARQ
        # ============================================

            
        try:
            # Import uuid for generating job tracking ID
            
            # Connect to Redis
            redis_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
            
            # Generate tracking ID for progress (we'll pass this to the function)
            tracking_id = str(uuid.uuid4())
            
            # Enqueue job to ARQ (pass tracking_id as first param after ctx)
            job = await redis_pool.enqueue_job(
                "process_file_background",  # Function name
                tracking_id,                # tracking_id (for progress)
                content,                    # file_content
                file.filename,              # filename
                session_id                  # session_id
            )
            
            # Store mapping: ARQ job_id -> tracking_id for progress lookup
            await redis_pool.setex(
                f"arq:tracking:{job.job_id}",
                3600,
                tracking_id
            )
            
            await redis_pool.close()
            
            logger.info(f"Job queued: {job.job_id} (tracking_id: {tracking_id})")
            
            return {
                "status": "queued",
                "job_id": job.job_id,
                "session_id": session_id,
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
    
        # ============================================
        # EXISTING: Synchronous processing (keep for backward compatibility)
        # ============================================
        try:
            with propagate_session_id(session_id, file_name=file.filename[:100]):
                result = await asyncio.wait_for(
                    MultiReportHandler.process_multi_report_pdf(content, file.filename),
                    timeout=constants.REQUEST_TIMEOUT_SECONDS
                )
                
                logger.file_validation(file.filename, "success", "processed successfully")
                
                # Validate and clean response
                try:
                    cleaned_result = validate_and_clean_agent_response(result)
                    result = cleaned_result
                except Exception as e:
                    logger.warning(f"Failed to clean agent response: {str(e)}")
                
                # Cache result
                try:
                    cache_id = agent_cache.save_agent_output(result, session_id=session_id)
                    logger.cache_save(cache_id, "agent output")
                except Exception as e:
                    logger.warning(f"Failed to cache agent output: {str(e)}")
                
                # Flush Langfuse
                if LANGFUSE_CONFIGURED:
                    try:
                        trace_url = get_trace_url()
                        if trace_url:
                            logger.info(f"📊 Langfuse trace: {trace_url}")
                        flush_langfuse()
                    except Exception as e:
                        logger.debug(f"Could not get trace URL: {e}")
                
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