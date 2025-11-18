from fastapi import APIRouter, Depends, HTTPException
from src.generator.redis_pool import get_shared_redis_pool
from src.utils.clean_logger import get_clean_logger
from src.deps.security import require_api_key
from src.deps.user_context import get_user_id
from typing import Optional, Dict, Any, Tuple
import json
import pickle

router = APIRouter()
logger = get_clean_logger(__name__)


async def _get_tracking_id(redis_pool, job_id: str) -> Optional[str]:
    """Get tracking_id from Redis mapping"""
    try:
        tracking_data = await redis_pool.get(f"arq:tracking:{job_id}")
        if tracking_data:
            tracking_id = tracking_data.decode('utf-8') if isinstance(tracking_data, bytes) else tracking_data
            logger.info(f"[PROGRESS] Found tracking_id: {tracking_id} for job_id: {job_id}")
            return tracking_id
        else:
            logger.warning(f"[PROGRESS] No tracking_id found for job_id: {job_id}")
            return None
    except Exception as e:
        logger.error(f"[PROGRESS] Could not get tracking_id: {e}")
        return None


async def _check_job_existence(redis_pool, job_id: str) -> Tuple[bool, bool, bool]:
    """Check if job and result keys exist in Redis, and if job failed"""
    result_key = f"arq:result:{job_id}"
    job_key = f"arq:job:{job_id}"
    
    result_exists = await redis_pool.exists(result_key)
    job_exists = await redis_pool.exists(job_key)
    
    # Check if job failed by looking at the result structure
    is_failed = False
    if result_exists:
        try:
            result_data = await redis_pool.get(result_key)
            if result_data:
                raw_result = _deserialize_result_data(result_data)
                # ARQ stores failed jobs with exception in "e" field
                # NOTE: "f" field is the function name, NOT a failure indicator!
                if isinstance(raw_result, dict):
                    logger.debug(f"[PROGRESS] Checking job failure status, raw_result keys: {list(raw_result.keys())}")
                    # Check for exception field (ARQ stores exceptions here)
                    if "e" in raw_result:
                        is_failed = True
                        logger.warning(f"[PROGRESS] Job {job_id} has exception field 'e', marking as failed")
                    # Also check if result contains error status
                    elif "r" in raw_result:
                        worker_result = raw_result["r"]
                        if isinstance(worker_result, dict) and worker_result.get("status") == "failed":
                            is_failed = True
                            logger.warning(f"[PROGRESS] Job {job_id} worker result has status='failed', marking as failed")
                        else:
                            logger.debug(f"[PROGRESS] Job {job_id} worker result status: {worker_result.get('status') if isinstance(worker_result, dict) else 'N/A'}")
                    else:
                        logger.debug(f"[PROGRESS] Job {job_id} has no 'e' or 'r' field, assuming not failed")
        except Exception as e:
            logger.warning(f"[PROGRESS] Error checking job failure status for {job_id}: {e}")
            pass  # If we can't check, assume not failed
    
    logger.debug(f"[PROGRESS] Job existence check: job_exists={job_exists}, result_exists={result_exists}, is_failed={is_failed}")
    
    return job_exists, result_exists, is_failed


def _deserialize_result_data(result_data: bytes) -> Optional[Any]:
    """Deserialize result data from pickle or JSON"""
    raw_result = None
    
    # CRITICAL FIX: ARQ stores results as pickle (binary)
    # Always try pickle first (ARQ's default)
    try:
        if isinstance(result_data, bytes):
            raw_result = pickle.loads(result_data)
        else:
            # If somehow already decoded, try to encode back
            raw_result = pickle.loads(result_data.encode('latin1'))
    except Exception as pickle_error:
        logger.debug(f"Pickle deserialization failed: {pickle_error}")
        # Fallback: try JSON (shouldn't happen with ARQ)
        try:
            if isinstance(result_data, bytes):
                result_data = result_data.decode('utf-8')
            raw_result = json.loads(result_data)
        except Exception as json_error:
            logger.error(f"Could not parse result as pickle or JSON: {json_error}")
            raw_result = None
    
    return raw_result


def _extract_worker_result(raw_result: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Extract actual result from ARQ's result structure and worker's return value
    Also extracts error information if job failed
    
    Returns:
        Tuple of (result_dict, error_message)
    """
    if not raw_result:
        return None, None
    
    error_message = None
    
    # ARQ stores failed jobs with exception in "e" field
    # NOTE: "f" field is the function name (e.g., "process_file_background"), NOT a failure indicator!
    # ARQ result structure: {"t": timestamp, "f": function_name, "r": return_value, "e": exception_if_failed}
    if isinstance(raw_result, dict):
        # Check for exception field (ARQ stores exceptions here)
        if "e" in raw_result:
            # Exception stored in "e" field - this indicates job failure
            exception = raw_result["e"]
            if isinstance(exception, Exception):
                error_message = str(exception)
                # Get the original message if it's a chained exception
                if hasattr(exception, '__cause__') and exception.__cause__:
                    original_error = str(exception.__cause__)
                    if original_error and original_error != error_message:
                        error_message = f"{error_message}: {original_error}"
            elif isinstance(exception, str):
                error_message = exception
            elif isinstance(exception, (list, tuple)) and len(exception) > 0:
                # ARQ sometimes stores exceptions as tuples
                error_message = str(exception[0]) if len(exception) > 0 else "Job failed"
            else:
                error_message = f"Job failed: {str(exception)}"
            logger.error(f"[PROGRESS] Job failed with exception: {error_message}")
            return None, error_message
    
    # ARQ stores result in structure: {"t": timestamp, "f": function_name, "r": <actual_return_value>}
    # First, extract the actual return value from "r" field (ARQ's result field)
    if isinstance(raw_result, dict) and "r" in raw_result:
        logger.debug(f"[PROGRESS] Extracting from ARQ structure, keys before: {list(raw_result.keys())}")
        raw_result = raw_result["r"]
        logger.debug(f"[PROGRESS] Extracted from 'r' field, type: {type(raw_result)}, is_dict: {isinstance(raw_result, dict)}")
        if isinstance(raw_result, dict):
            logger.debug(f"[PROGRESS] Keys after extraction: {list(raw_result.keys())}")
    
    # Worker returns: {"status": "success", "result": {...}, "session_id": "...", "cache_id": "..."}
    # The UI expects the full result structure, so we need to return the "result" field
    # but preserve session_id and cache_id at the top level of the result
    if isinstance(raw_result, dict):
        # Check if worker returned error status
        if raw_result.get("status") == "failed":
            error_message = raw_result.get("error", raw_result.get("message", "Job processing failed"))
            logger.error(f"[PROGRESS] Worker returned failed status: {error_message}")
            return None, error_message
        
        if "result" in raw_result:
            # Extract the actual processing result
            result = raw_result["result"]
            logger.debug(f"[PROGRESS] Found 'result' field, type: {type(result)}, is_dict: {isinstance(result, dict)}")
            
            # Ensure result is a dict
            if not isinstance(result, dict):
                logger.warning(f"[PROGRESS] Result is not a dict, converting to empty dict. Type: {type(result)}")
                result = {}
            
            # Preserve session_id and cache_id from worker's return at the top level
            # This is what the UI expects
            if "session_id" in raw_result:
                result["session_id"] = raw_result["session_id"]
            if "cache_id" in raw_result:
                result["cache_id"] = raw_result["cache_id"]
            
            # Also preserve status if present
            if "status" in raw_result:
                result["status"] = raw_result["status"]
            
            logger.debug(f"[PROGRESS] Returning extracted result with keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            return result, None
        else:
            # If no "result" field, use raw_result as-is (might already be the final result)
            logger.debug(f"[PROGRESS] No 'result' field found, using raw_result as-is. Keys: {list(raw_result.keys()) if isinstance(raw_result, dict) else 'N/A'}")
            return raw_result, None
    
    logger.warning(f"[PROGRESS] raw_result is not a dict after extraction, type: {type(raw_result)}, returning None")
    return None, None


async def _get_completed_result(redis_pool, job_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Get and deserialize completed job result from Redis
    Also extracts error information if job failed
    
    Returns:
        Tuple of (result_dict, error_message)
    """
    result_key = f"arq:result:{job_id}"
    
    try:
        result_data = await redis_pool.get(result_key)
        if not result_data:
            logger.warning(f"[PROGRESS] Result key exists but no data found for job_id: {job_id}")
            return None, None
        
        logger.debug(f"[PROGRESS] Deserializing result data for job_id: {job_id}, data type: {type(result_data)}")
        raw_result = _deserialize_result_data(result_data)
        if not raw_result:
            logger.warning(f"[PROGRESS] Failed to deserialize result data for job_id: {job_id}")
            return None, "Failed to deserialize job result"
        
        logger.debug(f"[PROGRESS] Extracting worker result, raw_result type: {type(raw_result)}, keys: {list(raw_result.keys()) if isinstance(raw_result, dict) else 'N/A'}")
        result, error_message = _extract_worker_result(raw_result)
        
        if error_message:
            # Job failed - return error
            logger.error(f"[PROGRESS] Job {job_id} failed: {error_message}")
            return None, error_message
        
        if result:
            # CRITICAL FIX: Ensure no bytes objects remain in result
            result = _convert_bytes_to_str(result)
            logger.info(f"[PROGRESS] Successfully extracted result for job_id: {job_id}, result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        else:
            logger.warning(f"[PROGRESS] Failed to extract worker result for job_id: {job_id}, raw_result: {type(raw_result)}")
        
        return result, None
    except Exception as e:
        logger.error(f"[PROGRESS] Failed to deserialize result for job_id {job_id}: {e}", exc_info=True)
        return None, f"Failed to retrieve job result: {str(e)}"


async def _get_progress_data(redis_pool, tracking_id: str) -> Tuple[int, str]:
    """Get progress and message from Redis for a tracking_id"""
    if not tracking_id:
        return 0, ""
    
    try:
        progress_data = await redis_pool.get(f"arq:progress:{tracking_id}")
        if progress_data:
            if isinstance(progress_data, bytes):
                progress_data = progress_data.decode('utf-8')
            progress_info = json.loads(progress_data)
            progress = progress_info.get("progress", 0)
            message = progress_info.get("message", "")
            
            # Ensure progress is an integer
            try:
                progress = int(progress)
            except (ValueError, TypeError):
                progress = 0
            
            logger.info(f"[PROGRESS] Retrieved progress: {progress}%, message: {message} for tracking_id: {tracking_id}")
            return progress, message
        else:
            # No progress data found - this is normal since we removed progress tracking
            logger.debug(f"[PROGRESS] No progress data found for tracking_id: {tracking_id}")
            return 0, ""
    except Exception as e:
        logger.error(f"[PROGRESS] Could not get custom progress: {e}")
        return 0, ""


def _normalize_progress_and_message(progress: int, message: str, job_status: str) -> Tuple[int, str]:
    """Normalize progress value and set default messages based on job status"""
    # Set default message if no progress data yet
    if not message and job_status == "in_progress":
        message = "Processing in progress..."
    
    # If complete but no custom progress, set to 100%
    if job_status == "complete" and progress == 0:
        progress = 100
        message = "Complete!"
    
    # Ensure progress is always an integer between 0-100
    try:
        progress = int(progress)
        progress = max(0, min(100, progress))  # Clamp between 0-100
    except (ValueError, TypeError):
        progress = 0
    
    return progress, message


@router.get("/progress/{job_id}")
async def get_progress(
    job_id: str, 
    user_id: str = Depends(get_user_id),  # ✅ Extract user_id from header
    api_key: str = Depends(require_api_key)
):
    """
    Get progress of background job
    
    Headers Required:
        X-User-ID: User identifier (must match job owner)
    
    Returns:
    {
        "job_id": str,
        "status": "queued" | "in_progress" | "complete" | "failed",
        "progress": int (0-100),
        "message": str,
        "result": dict (if complete)
    }
    """
    try:
        redis_pool = await get_shared_redis_pool()
        
        # ✅ Verify job belongs to user
        stored_user_id = await redis_pool.get(f"arq:user:{job_id}")
        if stored_user_id:
            stored_user_id = stored_user_id.decode('utf-8') if isinstance(stored_user_id, bytes) else stored_user_id
            if stored_user_id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="Job does not belong to this user"
                )
        
        # Get tracking_id from mapping
        tracking_id = await _get_tracking_id(redis_pool, job_id)
        
        # Check job existence and failure status
        job_exists, result_exists, is_failed = await _check_job_existence(redis_pool, job_id)
        
        if not job_exists and not result_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )
        
        # Initialize variables
        message = ""  # Initialize message to avoid UnboundLocalError
        progress = 0
        result = None
        error_message = None
        job_status = "in_progress"  # Default status
        
        # Determine job status and get result/error if complete
        if is_failed or result_exists:
            # Only fetch result if result exists (don't fetch if only is_failed is True)
            if result_exists:
                result, error_message = await _get_completed_result(redis_pool, job_id)
                logger.debug(f"[PROGRESS] Fetched result for job_id: {job_id}, result is None: {result is None}, error_message: {error_message}")
            else:
                result, error_message = None, None
            
            # Determine job status based on result extraction
            # Priority: error_message > result existence > is_failed flag
            if error_message:
                # Result extraction found an error - job definitely failed
                job_status = "failed"
                message = error_message
                progress = 0  # Reset progress on failure
                logger.warning(f"[PROGRESS] Job {job_id} marked as failed due to error_message: {error_message}")
            elif result_exists and result is not None:
                # Successfully extracted result - job is complete
                job_status = "complete"
                logger.info(f"[PROGRESS] Job {job_id} marked as complete, result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            elif is_failed:
                # is_failed flag is set but no error_message - might be a false positive, but trust the flag
                job_status = "failed"
                message = "Job processing failed"
                progress = 0
                logger.warning(f"[PROGRESS] Job {job_id} marked as failed due to is_failed flag (no error_message)")
            elif result_exists and result is None:
                # Result exists but extraction returned None - might be in progress or extraction failed
                logger.warning(f"[PROGRESS] Job {job_id} has result key but result extraction returned None")
                job_status = "in_progress"
            else:
                job_status = "in_progress"
        else:
            job_status = "in_progress"
            result = None
            error_message = None
        
        # Get progress data (only if not failed)
        if job_status != "failed":
            progress, progress_message = await _get_progress_data(redis_pool, tracking_id)
            if progress_message:
                message = progress_message
        else:
            progress = 0
        
        # Normalize progress and message
        if job_status != "failed":
            progress, message = _normalize_progress_and_message(progress, message, job_status)
        
        # Build response
        progress_info = {
            "job_id": job_id,
            "status": job_status,
            "progress": progress,
            "message": message
        }
        
        # Include error information if failed
        if job_status == "failed":
            # Ensure error message is user-friendly
            from src.utils.user_friendly_errors import get_user_friendly_error
            raw_error = error_message or message
            user_friendly_error = get_user_friendly_error(raw_error)
            
            progress_info["error"] = user_friendly_error
            progress_info["message"] = user_friendly_error
            # Keep raw error in a separate field for debugging (optional, can be removed)
            logger.error(f"[PROGRESS] Job {job_id} failed (technical): {raw_error}")
        # Include result if complete and successful
        elif result_exists and result is not None:
            progress_info["result"] = result
            logger.info(f"[PROGRESS] Returning progress: {progress}%, status: {job_status}, result included: {bool(result)}")
        else:
            logger.info(f"[PROGRESS] Returning progress: {progress}%, status: {job_status}, no result yet")
        
        return progress_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job progress: {str(e)}"
        )


def _convert_bytes_to_str(obj):
    """Recursively convert bytes to strings in nested structures"""
    if isinstance(obj, bytes):
        try:
            return obj.decode('utf-8')
        except UnicodeDecodeError:
            # If UTF-8 fails, try latin1 or return hex representation
            try:
                return obj.decode('latin1')
            except:
                return obj.hex()
    elif isinstance(obj, dict):
        return {k: _convert_bytes_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_bytes_to_str(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(_convert_bytes_to_str(item) for item in obj)
    else:
        return obj