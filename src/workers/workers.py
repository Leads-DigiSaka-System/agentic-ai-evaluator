from arq.connections import RedisSettings
from src.utils.config import REDIS_URL
from src.Upload.multiple_handler import MultiReportHandler
from src.utils.clean_logger import get_clean_logger
from src.services.cache_service import agent_cache
from src.generator.redis_pool import get_shared_redis_pool
import json
import asyncio
import time

logger = get_clean_logger(__name__)

# Helper function to update progress in Redis
async def update_progress(ctx, job_id: str, progress: int, message: str):
    """Update job progress in Redis"""
    try:
        # Try ARQ context Redis first (ARQ context is a dict-like object)
        redis = None
        if ctx:
            try:
                # ARQ context provides redis as ctx['redis'] or ctx.get('redis')
                redis = ctx.get('redis') if hasattr(ctx, 'get') else (ctx['redis'] if 'redis' in ctx else None)
            except (KeyError, AttributeError, TypeError) as ctx_error:
                logger.debug(f"[WORKER] Could not get Redis from context: {ctx_error}")
        
        # Fallback to shared Redis pool if context Redis not available
        if not redis:
            try:
                redis = await get_shared_redis_pool()
            except Exception as pool_error:
                logger.warning(f"[WORKER] Could not get shared Redis pool: {pool_error}")
        
        if redis:
            progress_data = {
                "progress": progress,
                "message": message
            }
            progress_key = f"arq:progress:{job_id}"
            await redis.setex(
                progress_key,
                3600,  # 1 hour TTL
                json.dumps(progress_data)
            )
            # Verify the write was successful
            try:
                stored_data = await redis.get(progress_key)
                if stored_data:
                    if isinstance(stored_data, bytes):
                        stored_data = stored_data.decode('utf-8')
                    stored_progress = json.loads(stored_data).get("progress", 0)
                    if stored_progress == progress:
                        logger.info(f"[WORKER] Progress updated: {progress}% - {message} (tracking_id: {job_id})")
                    else:
                        logger.warning(f"[WORKER] Progress write mismatch: wrote {progress}% but Redis has {stored_progress}% (tracking_id: {job_id})")
                else:
                    logger.error(f"[WORKER] Progress write failed: key not found after write (tracking_id: {job_id})")
            except Exception as verify_error:
                logger.warning(f"[WORKER] Could not verify progress write: {verify_error} (tracking_id: {job_id})")
        else:
            logger.error(f"[WORKER] No Redis connection available (context or pool)")
    except Exception as e:
        logger.error(f"[WORKER] Failed to update progress: {e}", exc_info=True)

# ARQ Worker Functions
# IMPORTANT: Must be standalone async functions (not class methods)
# Function name must match the string used in enqueue_job()

async def process_file_background(ctx, tracking_id: str, file_content: bytes, filename: str, session_id: str):
    """
    Process file in background
    
    Args:
        ctx: ARQ context (contains Redis connection)
        tracking_id: Unique tracking ID for job tracking
        file_content: File bytes
        filename: Original filename
        session_id: Session ID for tracking
        
    Returns:
        dict: Processing result
    """
    start_time = time.time()
    logger.info(f"Starting background processing: {filename} (tracking_id: {tracking_id})")
    
    try:
        # Start processing task
        processing_task = asyncio.create_task(
            MultiReportHandler.process_multi_report_pdf(
                file_content, 
                filename,
                tracking_id=tracking_id
            )
        )
        
        # Wait for processing to complete
        result = await processing_task
        
        logger.info(f"Tracking {tracking_id}: Complete! (Total time: {time.time() - start_time:.2f}s)")
        
        # Cache the result for storage approval (same as synchronous processing)
        # This ensures the result persists until user approval
        cache_id = None
        try:
            cache_id = await agent_cache.save_agent_output(result, session_id=session_id)
            logger.info(f"Result cached with cache_id: {cache_id} (tracking_id: {tracking_id})")
            # Add cache_id to result for frontend
            if isinstance(result, dict):
                result["cache_id"] = cache_id
        except Exception as e:
            logger.warning(f"Failed to cache result for storage approval: {e}")
            # Continue even if caching fails - result is still in ARQ result key
        
        return {
            "status": "success",
            "result": result,
            "session_id": session_id,
            "cache_id": cache_id  # Include cache_id for storage approval
        }
        
    except Exception as e:
        logger.error(f"Background processing failed: {e}")
        raise  # Re-raise to mark job as failed

# ARQ Worker Settings
class WorkerSettings:
    """
    ARQ Worker Configuration
    
    IMPORTANT: Class name dapat "WorkerSettings" (required by ARQ)
    """
    functions = [process_file_background]  # List of functions to register (standalone functions)
    redis_settings = RedisSettings.from_dsn(REDIS_URL)  # Redis connection
    from src.utils.constants import ARQ_MAX_JOBS, ARQ_JOB_TIMEOUT_SECONDS, ARQ_KEEP_RESULT_SECONDS
    max_jobs = ARQ_MAX_JOBS
    job_timeout = ARQ_JOB_TIMEOUT_SECONDS
    keep_result = ARQ_KEEP_RESULT_SECONDS