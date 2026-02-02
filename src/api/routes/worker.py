"""
Worker health check and metrics endpoints for ARQ background jobs.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.deps.security import require_api_key
from src.shared.limiter_config import limiter
from src.infrastructure.redis.redis_pool import get_shared_redis_pool
from src.shared.logging.clean_logger import get_clean_logger
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

router = APIRouter()
logger = get_clean_logger(__name__)


@router.get("/worker/health")
@limiter.limit("30/minute")
async def worker_health(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Check worker health and status
    
    Returns:
        {
            "status": "healthy" | "degraded" | "unhealthy",
            "worker_running": bool,
            "queue_length": int,
            "failed_jobs": int,
            "active_jobs": int,
            "redis_connected": bool,
            "timestamp": str
        }
    """
    try:
        redis_pool = await get_shared_redis_pool()
        
        # Check Redis connection
        try:
            await redis_pool.ping()
            redis_connected = True
        except Exception:
            redis_connected = False
        
        # Get queue statistics
        queue_length = 0
        failed_jobs = 0
        active_jobs = 0
        
        try:
            # Get all job keys
            job_keys = await redis_pool.keys("arq:job:*")
            queue_length = len(job_keys)
            
            # Count active jobs (jobs that are in progress)
            for job_key in job_keys:
                try:
                    job_data = await redis_pool.get(job_key)
                    if job_data:
                        # ARQ stores job status in the job data
                        # Active jobs are those that exist but don't have results yet
                        job_id = job_key.decode() if isinstance(job_key, bytes) else job_key
                        job_id = job_id.replace("arq:job:", "")
                        result_key = f"arq:result:{job_id}"
                        result_exists = await redis_pool.exists(result_key)
                        if not result_exists:
                            active_jobs += 1
                except Exception:
                    pass
            
            # Count failed jobs (jobs with error results)
            failed_keys = await redis_pool.keys("arq:result:*")
            for failed_key in failed_keys:
                try:
                    result_data = await redis_pool.get(failed_key)
                    if result_data:
                        # Try to deserialize and check for error status
                        import pickle
                        try:
                            result = pickle.loads(result_data) if isinstance(result_data, bytes) else pickle.loads(result_data.encode('latin1'))
                            if isinstance(result, dict) and result.get("r"):
                                worker_result = result.get("r", {})
                                if isinstance(worker_result, dict) and worker_result.get("status") == "failed":
                                    failed_jobs += 1
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Could not get queue statistics: {e}")
        
        # Determine overall health status
        if not redis_connected:
            status = "unhealthy"
        elif failed_jobs > 10 or queue_length > 100:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "worker_running": redis_connected,  # Assume worker is running if Redis is connected
            "queue_length": queue_length,
            "failed_jobs": failed_jobs,
            "active_jobs": active_jobs,
            "redis_connected": redis_connected,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Worker health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Worker health check failed: {str(e)}"
        )


@router.get("/worker/metrics")
@limiter.limit("30/minute")
async def worker_metrics(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Get detailed worker metrics
    
    Returns:
        {
            "queue_stats": {...},
            "job_stats": {...},
            "performance": {...}
        }
    """
    try:
        redis_pool = await get_shared_redis_pool()
        
        # Queue statistics
        job_keys = await redis_pool.keys("arq:job:*")
        result_keys = await redis_pool.keys("arq:result:*")
        progress_keys = await redis_pool.keys("arq:progress:*")
        tracking_keys = await redis_pool.keys("arq:tracking:*")
        
        # Count jobs by status
        queued = 0
        completed = 0
        failed = 0
        
        for job_key in job_keys:
            job_id = job_key.decode() if isinstance(job_key, bytes) else job_key
            job_id = job_id.replace("arq:job:", "")
            result_key = f"arq:result:{job_id}"
            if await redis_pool.exists(result_key):
                completed += 1
            else:
                queued += 1
        
        # Estimate failed jobs (jobs with error in result)
        for result_key in result_keys[:50]:  # Sample first 50 for performance
            try:
                result_data = await redis_pool.get(result_key)
                if result_data:
                    import pickle
                    try:
                        result = pickle.loads(result_data) if isinstance(result_data, bytes) else pickle.loads(result_data.encode('latin1'))
                        if isinstance(result, dict) and result.get("r"):
                            worker_result = result.get("r", {})
                            if isinstance(worker_result, dict) and worker_result.get("status") == "failed":
                                failed += 1
                    except Exception:
                        pass
            except Exception:
                pass
        
        return {
            "queue_stats": {
                "queued_jobs": queued,
                "completed_jobs": completed,
                "failed_jobs": failed,
                "total_jobs": queued + completed + failed
            },
            "redis_keys": {
                "job_keys": len(job_keys),
                "result_keys": len(result_keys),
                "progress_keys": len(progress_keys),
                "tracking_keys": len(tracking_keys)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get worker metrics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get worker metrics: {str(e)}"
        )


@router.get("/worker/jobs")
@limiter.limit("30/minute")
async def list_jobs(
    request: Request,
    status: Optional[str] = None,
    limit: int = 20,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    List recent jobs with optional status filter
    
    Args:
        status: Filter by status ("queued", "completed", "failed")
        limit: Maximum number of jobs to return
        
    Returns:
        {
            "jobs": [...],
            "total": int
        }
    """
    try:
        redis_pool = await get_shared_redis_pool()
        
        jobs = []
        job_keys = await redis_pool.keys("arq:job:*")
        
        for job_key in job_keys[:limit]:
            try:
                job_id = job_key.decode() if isinstance(job_key, bytes) else job_key
                job_id = job_id.replace("arq:job:", "")
                
                # Get job status
                result_key = f"arq:result:{job_id}"
                result_exists = await redis_pool.exists(result_key)
                
                job_status = "completed" if result_exists else "queued"
                
                # Get tracking ID
                tracking_key = f"arq:tracking:{job_id}"
                tracking_data = await redis_pool.get(tracking_key)
                tracking_id = tracking_data.decode() if tracking_data and isinstance(tracking_data, bytes) else (tracking_data if tracking_data else None)
                
                # Apply status filter
                if status and job_status != status:
                    continue
                
                jobs.append({
                    "job_id": job_id,
                    "tracking_id": tracking_id,
                    "status": job_status,
                    "created_at": None  # ARQ doesn't store creation time directly
                })
            except Exception as e:
                logger.debug(f"Error processing job {job_key}: {e}")
                continue
        
        return {
            "jobs": jobs,
            "total": len(jobs),
            "filtered_by": status
        }
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list jobs: {str(e)}"
        )

