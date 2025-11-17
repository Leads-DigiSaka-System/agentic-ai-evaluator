from fastapi import APIRouter, Depends, HTTPException
from src.generator.redis_pool import get_shared_redis_pool
from src.utils.clean_logger import get_clean_logger
from src.deps.security import require_api_key
import json
import pickle

router = APIRouter()
logger = get_clean_logger(__name__)

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
        
        # Get tracking_id from mapping first
        tracking_id = None
        try:
            tracking_data = await redis_pool.get(f"arq:tracking:{job_id}")
            if tracking_data:
                tracking_id = tracking_data.decode('utf-8') if isinstance(tracking_data, bytes) else tracking_data
                logger.info(f"[PROGRESS] Found tracking_id: {tracking_id} for job_id: {job_id}")
            else:
                logger.warning(f"[PROGRESS] No tracking_id found for job_id: {job_id}")
        except Exception as e:
            logger.error(f"[PROGRESS] Could not get tracking_id: {e}")
        
        # Check result key FIRST
        result_key = f"arq:result:{job_id}"
        result_exists = await redis_pool.exists(result_key)
        
        # Check if job key exists (for in-progress jobs)
        job_key = f"arq:job:{job_id}"
        job_exists = await redis_pool.exists(job_key)
        
        if not job_exists and not result_exists:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )
        
        job_status = "in_progress"
        result = None
        
        if result_exists:
            job_status = "complete"
            try:
                result_data = await redis_pool.get(result_key)
                if result_data:
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
                    
                    if raw_result:
                        # ARQ stores result in structure: {"t": ..., "f": ..., "r": <actual_return_value>}
                        # First, extract the actual return value from "r" field (ARQ's result field)
                        if isinstance(raw_result, dict) and "r" in raw_result:
                            # ARQ stores actual return value in "r" field
                            raw_result = raw_result["r"]
                        
                        # Now extract the actual result from worker's return value
                        # Worker returns: {"status": "success", "result": {...}, "session_id": "...", "cache_id": "..."}
                        if isinstance(raw_result, dict) and "result" in raw_result:
                            result = raw_result["result"]
                            # Preserve session_id and cache_id from worker's return
                            if not isinstance(result, dict):
                                result = {}
                            if "session_id" in raw_result:
                                result["session_id"] = raw_result["session_id"]
                            if "cache_id" in raw_result:
                                result["cache_id"] = raw_result["cache_id"]
                        else:
                            # If no "result" field, use raw_result as-is (might already be the final result)
                            result = raw_result
                        
                        # CRITICAL FIX: Ensure no bytes objects remain in result
                        # Convert any bytes to strings recursively
                        result = _convert_bytes_to_str(result)
                    else:
                        result = None
            except Exception as e:
                logger.error(f"Failed to deserialize result: {e}")
                result = None
        
        # Get progress from Redis (custom progress storage)
        progress = 0
        message = ""
        if tracking_id:
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
                else:
                    # No progress data found - this is normal since we removed progress tracking
                    # Just log at debug level instead of warning
                    logger.debug(f"[PROGRESS] No progress data found for tracking_id: {tracking_id}")
            except Exception as e:
                logger.error(f"[PROGRESS] Could not get custom progress: {e}")
        
        # Set default message if no progress data yet
        if not message and job_status == "in_progress":
            message = "Processing in progress..."
            # Don't set fake progress - return 0% since we removed progress tracking
        
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
        
        progress_info = {
            "job_id": job_id,
            "status": job_status,
            "progress": progress,  # Ensure integer
            "message": message,
            "result": result
        }
        
        logger.info(f"[PROGRESS] Returning progress: {progress}%, status: {job_status}, message: {message}")
        
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