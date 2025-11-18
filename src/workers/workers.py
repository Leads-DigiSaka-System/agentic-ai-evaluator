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
            from src.utils.constants import REDIS_PROGRESS_TTL_SECONDS
            progress_key = f"arq:progress:{job_id}"
            await redis.setex(
                progress_key,
                REDIS_PROGRESS_TTL_SECONDS,
                json.dumps(progress_data)
            )
            # Simplified logging - removed verification overhead
            logger.info(f"[WORKER] Progress updated: {progress}% - {message} (tracking_id: {job_id})")
        else:
            logger.error(f"[WORKER] No Redis connection available (context or pool)")
    except Exception as e:
        logger.error(f"[WORKER] Failed to update progress: {e}", exc_info=True)

# ARQ Worker Functions
# IMPORTANT: Must be standalone async functions (not class methods)
# Function name must match the string used in enqueue_job()

async def process_file_background(ctx, tracking_id: str, file_content: bytes, filename: str, session_id: str, user_id: str):
    """
    Process file in background with user isolation
    
    Args:
        ctx: ARQ context (contains Redis connection)
        tracking_id: Unique tracking ID for job tracking
        file_content: File bytes
        filename: Original filename
        session_id: Session ID for tracking
        user_id: User ID for data isolation
        
    Returns:
        dict: Processing result
    """
    start_time = time.time()
    logger.info(f"Starting background processing for user {user_id}: {filename} (tracking_id: {tracking_id})")
    
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
        
        # Cache the result for storage approval (with user_id for isolation)
        # This ensures the result persists until user approval
        cache_id = None
        try:
            cache_id = await agent_cache.save_agent_output(result, session_id=session_id, user_id=user_id)
            logger.info(f"Result cached with cache_id: {cache_id} (tracking_id: {tracking_id}, user: {user_id})")
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
            "cache_id": cache_id,  # Include cache_id for storage approval
            "user_id": user_id  # ✅ Include user_id in response
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Background processing failed for {filename} (tracking_id: {tracking_id}): {error_message}", exc_info=True)
        
        # Import user-friendly error utility
        from src.utils.user_friendly_errors import get_user_friendly_error
        
        # Create a user-friendly error message
        # ARQ will store the exception in the "e" field, which our progress endpoint will extract
        user_friendly_error = get_user_friendly_error(error_message)
        
        # Raise exception so ARQ marks job as failed and can retry
        # The exception message will be stored and can be retrieved by progress endpoint
        raise Exception(user_friendly_error) from e

# ARQ Worker Settings
class WorkerSettings:
    """
    ARQ Worker Configuration with retry mechanism
    
    IMPORTANT: Class name dapat "WorkerSettings" (required by ARQ)
    """
    functions = [process_file_background]  # List of functions to register (standalone functions)
    redis_settings = RedisSettings.from_dsn(REDIS_URL)  # Redis connection
    from src.utils.constants import (
        ARQ_MAX_JOBS, 
        ARQ_JOB_TIMEOUT_SECONDS, 
        ARQ_KEEP_RESULT_SECONDS,
        ARQ_MAX_RETRIES,
        ARQ_RETRY_DELAY
    )
    max_jobs = ARQ_MAX_JOBS
    job_timeout = ARQ_JOB_TIMEOUT_SECONDS
    keep_result = ARQ_KEEP_RESULT_SECONDS
    # Retry configuration
    retry_jobs = True  # Enable automatic retries for failed jobs
    max_retries = ARQ_MAX_RETRIES  # Maximum number of retry attempts
    retry_delay = ARQ_RETRY_DELAY  # Delay between retries (seconds)