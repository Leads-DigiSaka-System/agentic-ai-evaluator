from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from src.Upload.multiple_handler import MultiReportHandler
from src.utils import constants
from src.utils.limiter_config import limiter
from src.utils.errors import ProcessingError, ValidationError
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
import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from src.utils.clean_logger import get_clean_logger

router = APIRouter()
logger = get_clean_logger(__name__)


@router.post("/agent")
@limiter.limit("10/minute")
@observe_operation(name="agent_file_upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """
    Upload and process agricultural demo reports
    
    Supports:
    - PDF files (single or multi-report)
    - Image files (PNG, JPG, JPEG)
    
    Security Features:
    - File validation (type, size, filename security)
    - Request timeout protection
    - Rate limiting (10 requests/minute)
    - Comprehensive error handling
    """
    try:
        # Read file content
        content = await file.read()
        
        # Comprehensive file validation
        validate_and_raise(file.filename, content, field_name="file")
        
        logger.file_upload(file.filename, len(content))
        
        # Generate session ID for this file upload
        # This will group all traces (extraction, validation, analysis per report, etc.)
        # into one session for easy tracking
        session_id = generate_session_id(prefix="file_upload")
        logger.info(f"Generated session ID: {session_id}")
        
        # Set session_id on the current trace (created by @observe_operation)
        if LANGFUSE_CONFIGURED:
            try:
                client = get_langfuse_client()
                if client:
                    client.update_current_trace(
                        session_id=session_id,
                        metadata={"file_name": file.filename[:100], "session_id": session_id}
                    )
                    logger.debug(f"Session ID set on trace: {session_id}")
            except Exception as e:
                logger.warning(f"Failed to set session_id on trace: {e}")
        
        # Process with timeout protection
        # All traces created within this context will inherit the session_id
        try:
            with propagate_session_id(session_id, file_name=file.filename[:100]):
                result = await asyncio.wait_for(
                    MultiReportHandler.process_multi_report_pdf(content, file.filename),
                    timeout=constants.REQUEST_TIMEOUT_SECONDS
                )
            
            logger.file_validation(file.filename, "success", "processed successfully")
            
            # Validate and clean the response structure
            try:
                cleaned_result = validate_and_clean_agent_response(result)
                logger.info("Agent response validated and cleaned")
                result = cleaned_result
            except Exception as e:
                logger.warning(f"Failed to clean agent response: {str(e)}")
                # Continue with original result if cleaning fails
            
            # Automatically cache the result for storage (with session_id for linking)
            try:
                cache_id = agent_cache.save_agent_output(result, session_id=session_id)
                logger.cache_save(cache_id, "agent output")
                logger.debug(f"Cached with session_id: {session_id}")
            except Exception as e:
                logger.warning(f"Failed to cache agent output: {str(e)}")
                # Don't fail the request if caching fails
            
            # Log session info and flush Langfuse
            if LANGFUSE_CONFIGURED:
                try:
                    trace_url = get_trace_url()
                    if trace_url:
                        logger.info(f"📊 Langfuse trace: {trace_url}")
                    logger.info(f"📦 Session ID: {session_id}")
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
        # Re-raise custom errors as-is
        raise
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Catch unexpected errors and provide context
        logger.error(f"Unexpected error processing file: {str(e)[:100]}")
        raise ProcessingError(
            detail=f"Unexpected error during file processing",
            step="file_upload",
            file_name=file.filename[:50] if file.filename else "unknown",
            error=str(e)[:200]
        )