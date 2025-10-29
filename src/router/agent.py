from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from src.Upload.multiple_handler import MultiReportHandler
from src.utils import constants
from src.utils.limiter_config import limiter
from src.utils.errors import ProcessingError, ValidationError
from src.utils.file_validator import validate_and_raise, FileValidator
from src.services.cache_service import agent_cache
from src.formatter.json_helper import validate_and_clean_agent_response
import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from src.utils.clean_logger import get_clean_logger

router = APIRouter()
logger = get_clean_logger(__name__)


@router.post("/agent")
@limiter.limit("10/minute")
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
        
        # Process with timeout protection
        try:
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
            
            # Automatically cache the result for storage
            try:
                cache_id = agent_cache.save_agent_output(result)
                logger.cache_save(cache_id, "agent output")
            except Exception as e:
                logger.warning(f"Failed to cache agent output: {str(e)}")
                # Don't fail the request if caching fails
            
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