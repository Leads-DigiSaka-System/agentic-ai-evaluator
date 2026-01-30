
from arq import create_pool
from arq.connections import RedisSettings
from src.core.config import REDIS_URL, REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD
from src.shared.logging.clean_logger import get_clean_logger
from typing import Optional
import asyncio
import json

logger = get_clean_logger(__name__)

class RedisPoolManager:
    """
    Singleton Redis Pool Manager
    
    Manages a single Redis connection pool that can be reused across the application.
    This eliminates the need to create/close pools repeatedly.
    """
    _instance: Optional['RedisPoolManager'] = None
    _pool = None
    _redis_url: str = None
    _lock: Optional[asyncio.Lock] = None
    
    def __new__(cls, redis_url: str = None):
        """Singleton pattern - ensures only one instance exists"""
        if cls._instance is None:
            cls._instance = super(RedisPoolManager, cls).__new__(cls)
            cls._instance._redis_url = redis_url or REDIS_URL
            cls._instance._pool = None
            cls._instance._lock = asyncio.Lock()  # Lock for thread-safe pool creation
            logger.info(f"RedisPoolManager initialized with URL: {cls._instance._redis_url}")
        return cls._instance
    
    async def get_pool(self):
        """
        Get or create the shared Redis pool (thread-safe for multiple users)
        
        Uses asyncio.Lock to prevent race conditions when multiple requests
        try to create the pool simultaneously.
        
        Returns:
            Redis connection pool (ARQ Redis pool)
        """
        # Double-check pattern with lock for thread-safety
        if self._pool is None:
            async with self._lock:
                # Check again after acquiring lock (another request might have created it)
                if self._pool is None:
                    logger.info("Creating shared Redis connection pool...")
                    self._pool = await create_pool(RedisSettings.from_dsn(self._redis_url))
                    logger.info("Shared Redis pool created successfully")
        return self._pool
    
    async def close_pool(self):
        """Close the shared Redis pool"""
        if self._pool:
            logger.info("Closing shared Redis pool...")
            await self._pool.close()
            self._pool = None
            logger.info("Shared Redis pool closed")
    
    def is_pool_created(self) -> bool:
        """Check if pool is already created"""
        return self._pool is not None


# Global singleton instance
_redis_manager: Optional[RedisPoolManager] = None

def get_redis_manager(redis_url: str = None) -> RedisPoolManager:
    """
    Get the global Redis pool manager instance (singleton)
    
    Args:
        redis_url: Optional Redis URL (uses REDIS_URL from config if not provided)
        
    Returns:
        RedisPoolManager instance
    """
    global _redis_manager
    if _redis_manager is None:
        _redis_manager = RedisPoolManager(redis_url)
    return _redis_manager


async def get_shared_redis_pool():
    """
    Convenience function to get the shared Redis pool
    
    Usage:
        redis_pool = await get_shared_redis_pool()
        await redis_pool.setex("key", 3600, "value")
    
    Returns:
        Redis connection pool
    """
    manager = get_redis_manager()
    return await manager.get_pool()


async def close_shared_redis_pool():
    """
    Convenience function to close the shared Redis pool
    
    Call this during application shutdown
    """
    manager = get_redis_manager()
    await manager.close_pool()


# Synchronous Redis client for progress updates from sync nodes
_sync_redis_client = None

def get_sync_redis_client():
    """
    Get a synchronous Redis client for use in synchronous functions (like LangGraph nodes)
    
    This uses the standard redis package (not ARQ) for synchronous operations.
    """
    global _sync_redis_client
    if _sync_redis_client is None:
        try:
            import redis
            _sync_redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,  # Support password for Redis Cloud
                decode_responses=False  # Keep bytes for compatibility
            )
            # Test connection
            _sync_redis_client.ping()
            logger.info(f"Synchronous Redis client created: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")
        except ImportError:
            logger.warning("redis package not installed, progress updates from sync nodes will fail")
            return None
        except Exception as e:
            logger.error(f"Failed to create synchronous Redis client: {e}")
            return None
    return _sync_redis_client


def update_progress_sync(tracking_id: str, progress: int, message: str):
    """
    Synchronously update progress in Redis (for use in sync functions like LangGraph nodes)
    
    Args:
        tracking_id: Tracking ID for the job
        progress: Progress percentage (0-100)
        message: Progress message
    """
    if not tracking_id:
        return
    
    try:
        redis_client = get_sync_redis_client()
        if not redis_client:
            return  # Redis client not available
        
        progress_data = {
            "progress": progress,
            "message": message
        }
        
        # Use setex for synchronous operation
        from src.core.constants import REDIS_PROGRESS_TTL_SECONDS
        redis_client.setex(
            f"arq:progress:{tracking_id}",
            REDIS_PROGRESS_TTL_SECONDS,
            json.dumps(progress_data)
        )
        
    except Exception as e:
        logger.warning(f"Failed to update progress synchronously: {e}")

