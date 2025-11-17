from fastapi import APIRouter, Depends, HTTPException
from arq import create_pool
from arq.connections import RedisSettings
from src.utils.config import REDIS_URL
from src.utils.clean_logger import get_clean_logger
from src.deps.security import require_api_key
import json

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
        redis_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        
        # Get job from ARQ
        job = await redis_pool.get_job(job_id)
        
        if not job:
            await redis_pool.close()
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )
        
        # Get tracking_id from mapping
        tracking_id = None
        try:
            tracking_data = await redis_pool.get(f"arq:tracking:{job_id}")
            if tracking_data:
                tracking_id = tracking_data.decode() if isinstance(tracking_data, bytes) else tracking_data
        except Exception as e:
            logger.debug(f"Could not get tracking_id: {e}")
        
        # Get progress from Redis (custom progress storage)
        progress = 0
        message = ""
        if tracking_id:
            try:
                progress_data = await redis_pool.get(f"arq:progress:{tracking_id}")
                if progress_data:
                    progress_info = json.loads(progress_data.decode() if isinstance(progress_data, bytes) else progress_data)
                    progress = progress_info.get("progress", 0)
                    message = progress_info.get("message", "")
            except Exception as e:
                logger.debug(f"Could not get custom progress: {e}")
        
        # Get result if complete
        result = None
        if job.status == "complete":
            result = job.result
            # If complete but no custom progress, set to 100%
            if progress == 0:
                progress = 100
                message = "Complete!"
        
        # Get progress info
        progress_info = {
            "job_id": job_id,
            "status": job.status,
            "progress": progress,
            "message": message,
            "result": result
        }
        
        await redis_pool.close()
        return progress_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job progress: {str(e)}"
        )