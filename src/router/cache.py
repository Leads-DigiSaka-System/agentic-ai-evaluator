"""
Cache management endpoints for Redis cleanup and monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException
from src.deps.security import require_api_key
from src.services.cache_service import agent_cache
from src.generator.redis_pool import get_shared_redis_pool
from src.utils.clean_logger import get_clean_logger
from typing import Dict, Any
import asyncio

router = APIRouter()
logger = get_clean_logger(__name__)


@router.post("/cache/cleanup")
async def cleanup_expired_cache(api_key: str = Depends(require_api_key)) -> Dict[str, Any]:
    """
    Manually clean up expired cache entries from Redis
    
    This endpoint scans all cache entries and removes expired ones.
    Redis TTL handles expiration automatically, but this can clean up
    any entries that might have been missed.
    
    Returns:
        {
            "status": "success",
            "cleaned_count": int,
            "message": str
        }
    """
    try:
        logger.info("Starting manual cache cleanup...")
        cleaned_count = await agent_cache.cleanup_expired_caches()
        
        return {
            "status": "success",
            "cleaned_count": cleaned_count,
            "message": f"Cleaned up {cleaned_count} expired cache entries"
        }
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Cache cleanup failed: {str(e)}"
        )


@router.delete("/cache/clear-all")
async def clear_all_cache(api_key: str = Depends(require_api_key)) -> Dict[str, Any]:
    """
    ⚠️ DANGER: Clear ALL cache entries from Redis
    
    This will delete all cache entries regardless of expiration status.
    Use with caution!
    
    Returns:
        {
            "status": "success",
            "deleted_count": int,
            "message": str
        }
    """
    try:
        logger.warning("⚠️ Clearing ALL cache entries from Redis")
        redis_pool = await get_shared_redis_pool()
        
        # Get all cache keys
        cache_keys = await redis_pool.keys("agent:cache:*")
        deleted_count = 0
        
        for cache_key in cache_keys:
            # Decode key if bytes
            if isinstance(cache_key, bytes):
                cache_key = cache_key.decode()
            
            deleted = await redis_pool.delete(cache_key)
            if deleted:
                deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} cache entries")
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Cleared {deleted_count} cache entries"
        }
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.get("/cache/stats")
async def get_cache_stats(api_key: str = Depends(require_api_key)) -> Dict[str, Any]:
    """
    Get cache statistics from Redis
    
    Returns:
        {
            "total_entries": int,
            "total_size_mb": float,
            "oldest_entry": str,
            "newest_entry": str
        }
    """
    try:
        redis_pool = await get_shared_redis_pool()
        
        # Get all cache keys
        cache_keys = await redis_pool.keys("agent:cache:*")
        total_entries = len(cache_keys)
        
        # Get TTL info
        total_size_bytes = 0
        oldest_ttl = None
        newest_ttl = None
        
        for cache_key in cache_keys[:100]:  # Sample first 100 for performance
            if isinstance(cache_key, bytes):
                cache_key = cache_key.decode()
            
            ttl = await redis_pool.ttl(cache_key)
            if ttl > 0:
                if oldest_ttl is None or ttl < oldest_ttl:
                    oldest_ttl = ttl
                if newest_ttl is None or ttl > newest_ttl:
                    newest_ttl = ttl
            
            # Get size
            data = await redis_pool.get(cache_key)
            if data:
                total_size_bytes += len(data) if isinstance(data, bytes) else len(str(data))
        
        # Estimate total size (sample * total / sample_size)
        estimated_total_size = total_size_bytes * (total_entries / min(100, total_entries)) if total_entries > 0 else 0
        
        return {
            "status": "success",
            "total_entries": total_entries,
            "estimated_size_mb": round(estimated_total_size / (1024 * 1024), 2),
            "oldest_ttl_seconds": oldest_ttl,
            "newest_ttl_seconds": newest_ttl,
            "cache_expiry_hours": agent_cache.cache_expiry_hours
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache stats: {str(e)}"
        )


@router.delete("/cache/{cache_id}")
async def delete_specific_cache(
    cache_id: str, 
    api_key: str = Depends(require_api_key)
) -> Dict[str, Any]:
    """
    Delete a specific cache entry by cache_id
    
    ⚠️ ADMIN ONLY: This endpoint is for admin use only.
    
    Args:
        cache_id: Cache ID to delete
        
    Returns:
        {
            "status": "success" | "not_found",
            "cache_id": str,
            "message": str
        }
    """
    try:
        # Admin-only operation - no user_id filtering needed
        deleted = await agent_cache.delete_cache(cache_id)
        
        if deleted:
            return {
                "status": "success",
                "cache_id": cache_id,
                "message": f"Cache {cache_id} deleted successfully"
            }
        else:
            return {
                "status": "not_found",
                "cache_id": cache_id,
                "message": f"Cache {cache_id} not found"
            }
    except Exception as e:
        logger.error(f"Failed to delete cache {cache_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete cache: {str(e)}"
        )

