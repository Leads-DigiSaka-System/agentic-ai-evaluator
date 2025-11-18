from fastapi import APIRouter, Depends, HTTPException
from src.generator.redis_pool import get_shared_redis_pool
from src.utils.clean_logger import get_clean_logger
from src.deps.security import require_api_key
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


async def _check_job_existence(redis_pool, job_id: str) -> Tuple[bool, bool]:
    """Check if job and result keys exist in Redis"""
    result_key = f"arq:result:{job_id}"
    job_key = f"arq:job:{job_id}"
    
    result_exists = await redis_pool.exists(result_key)
    job_exists = await redis_pool.exists(job_key)
    
    return job_exists, result_exists


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


def _extract_worker_result(raw_result: Any) -> Optional[Dict[str, Any]]:
    """Extract actual result from ARQ's result structure and worker's return value"""
    if not raw_result:
        return None
    
    # ARQ stores result in structure: {"t": ..., "f": ..., "r": <actual_return_value>}
    # First, extract the actual return value from "r" field (ARQ's result field)
    if isinstance(raw_result, dict) and "r" in raw_result:
        raw_result = raw_result["r"]
    
    # Worker returns: {"status": "success", "result": {...}, "session_id": "...", "cache_id": "..."}
    # The UI expects the full result structure, so we need to return the "result" field
    # but preserve session_id and cache_id at the top level of the result
    if isinstance(raw_result, dict):
        if "result" in raw_result:
            # Extract the actual processing result
            result = raw_result["result"]
            
            # Ensure result is a dict
            if not isinstance(result, dict):
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
            
            return result
        else:
            # If no "result" field, use raw_result as-is (might already be the final result)
            return raw_result
    
    return None


async def _get_completed_result(redis_pool, job_id: str) -> Optional[Dict[str, Any]]:
    """Get and deserialize completed job result from Redis"""
    result_key = f"arq:result:{job_id}"
    
    try:
        result_data = await redis_pool.get(result_key)
        if not result_data:
            logger.warning(f"[PROGRESS] Result key exists but no data found for job_id: {job_id}")
            return None
        
        logger.debug(f"[PROGRESS] Deserializing result data for job_id: {job_id}, data type: {type(result_data)}")
        raw_result = _deserialize_result_data(result_data)
        if not raw_result:
            logger.warning(f"[PROGRESS] Failed to deserialize result data for job_id: {job_id}")
            return None
        
        logger.debug(f"[PROGRESS] Extracting worker result, raw_result type: {type(raw_result)}, keys: {list(raw_result.keys()) if isinstance(raw_result, dict) else 'N/A'}")
        result = _extract_worker_result(raw_result)
        if result:
            # CRITICAL FIX: Ensure no bytes objects remain in result
            result = _convert_bytes_to_str(result)
            logger.info(f"[PROGRESS] Successfully extracted result for job_id: {job_id}, result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        else:
            logger.warning(f"[PROGRESS] Failed to extract worker result for job_id: {job_id}, raw_result: {type(raw_result)}")
        
        return result
    except Exception as e:
        logger.error(f"[PROGRESS] Failed to deserialize result for job_id {job_id}: {e}", exc_info=True)
        return None


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
async def get_progress(job_id: str, api_key: str = Depends(require_api_key)):
    """
    Get progress of background job
    
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
        
        # Get tracking_id from mapping
        tracking_id = await _get_tracking_id(redis_pool, job_id)
        
        # Check job existence
        job_exists, result_exists = await _check_job_existence(redis_pool, job_id)
        
        if not job_exists and not result_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )
        
        # Determine job status and get result if complete
        job_status = "complete" if result_exists else "in_progress"
        result = await _get_completed_result(redis_pool, job_id) if result_exists else None
        
        # Get progress data
        progress, message = await _get_progress_data(redis_pool, tracking_id)
        
        # Normalize progress and message
        progress, message = _normalize_progress_and_message(progress, message, job_status)
        
        # Build response - ensure result is always included when complete
        progress_info = {
            "job_id": job_id,
            "status": job_status,
            "progress": progress,
            "message": message
        }
        
        # Only include result if it exists and job is complete
        if result_exists and result is not None:
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