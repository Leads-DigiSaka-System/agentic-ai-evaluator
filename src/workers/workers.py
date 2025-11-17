from arq.connections import RedisSettings
from src.utils.config import REDIS_URL
from src.Upload.multiple_handler import MultiReportHandler
from src.utils.clean_logger import get_clean_logger
import json

logger = get_clean_logger(__name__)

# Helper function to update progress in Redis
async def update_progress(ctx, job_id: str, progress: int, message: str):
    """Update job progress in Redis"""
    try:
        redis = ctx.get('redis')
        if redis:
            progress_data = {
                "progress": progress,
                "message": message
            }
            await redis.setex(
                f"arq:progress:{job_id}",
                3600,  # 1 hour TTL
                json.dumps(progress_data)
            )
    except Exception as e:
        logger.debug(f"Failed to update progress: {e}")

# ARQ Worker Functions
# IMPORTANT: Must be standalone async functions (not class methods)
# Function name must match the string used in enqueue_job()

async def process_file_background(ctx, tracking_id: str, file_content: bytes, filename: str, session_id: str):
    """
    Process file in background
    
    Args:
        ctx: ARQ context (contains Redis connection)
        tracking_id: Unique tracking ID for progress updates
        file_content: File bytes
        filename: Original filename
        session_id: Session ID for tracking
        
    Returns:
        dict: Processing result
    """
    logger.info(f"Starting background processing: {filename} (tracking_id: {tracking_id})")
    
    try:
        # Update progress: 0-20% (File validation)
        await update_progress(ctx, tracking_id, 10, "Validating file...")
        logger.info(f"Tracking {tracking_id}: Progress 10% - Validating file...")
        # Your validation logic here
        
        # Update progress: 20-40% (Extraction)
        await update_progress(ctx, tracking_id, 30, "Extracting content...")
        logger.info(f"Tracking {tracking_id}: Progress 30% - Extracting content...")
        # Your extraction logic here
        
        # Update progress: 40-60% (Analysis)
        await update_progress(ctx, tracking_id, 50, "Analyzing data...")
        logger.info(f"Tracking {tracking_id}: Progress 50% - Analyzing data...")
        result = await MultiReportHandler.process_multi_report_pdf(file_content, filename)
        
        # Update progress: 60-80% (Graph generation)
        await update_progress(ctx, tracking_id, 70, "Generating graphs...")
        logger.info(f"Tracking {tracking_id}: Progress 70% - Generating graphs...")
        # Graph generation happens in workflow
        
        # Update progress: 80-100% (Finalization)
        await update_progress(ctx, tracking_id, 90, "Finalizing...")
        logger.info(f"Tracking {tracking_id}: Progress 90% - Finalizing...")
        
        await update_progress(ctx, tracking_id, 100, "Complete!")
        logger.info(f"Tracking {tracking_id}: Progress 100% - Complete!")
        
        return {
            "status": "success",
            "result": result,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Background processing failed: {e}")
        await update_progress(ctx, tracking_id, 0, f"Error: {str(e)}")
        raise  # Re-raise to mark job as failed

# ARQ Worker Settings
class WorkerSettings:
    """
    ARQ Worker Configuration
    
    IMPORTANT: Class name dapat "WorkerSettings" (required by ARQ)
    """
    functions = [process_file_background]  # List of functions to register (standalone functions)
    redis_settings = RedisSettings.from_dsn(REDIS_URL)  # Redis connection
    max_jobs = 10  # Max concurrent jobs
    job_timeout = 600  # 10 minutes timeout per job
    keep_result = 3600  # Keep results in Redis for 1 hour