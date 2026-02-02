"""
Cache management endpoints for Redis cleanup and monitoring.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from src.api.deps.security import require_api_key
from src.shared.limiter_config import limiter
from src.services.cache_service import agent_cache
from src.infrastructure.redis.redis_pool import get_shared_redis_pool
from src.shared.logging.clean_logger import get_clean_logger
from src.monitoring.trace.langfuse_helper import is_langfuse_enabled
from typing import Dict, Any
import asyncio

if is_langfuse_enabled():
    from langfuse import observe, get_client
else:
    def observe(**kwargs):
        def decorator(fn):
            return fn
        return decorator
    def get_client():
        return None

router = APIRouter()
logger = get_clean_logger(__name__)


def _cache_trace_attrs(action: str, **extra):
    """Set Langfuse trace attributes for admin cache endpoints."""
    langfuse = get_client() if is_langfuse_enabled() else None
    if langfuse:
        try:
            langfuse.update_current_trace(
                tags=["admin", "cache", "api"],
                metadata={"action": action, **extra},
            )
        except Exception:
            pass


@router.post("/cache/cleanup")
@limiter.limit("10/minute")
@observe(name="cache_cleanup")
async def cleanup_expired_cache(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
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
        _cache_trace_attrs("cleanup")
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
@limiter.limit("5/minute")
@observe(name="cache_clear_all")
async def clear_all_cache(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
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
        _cache_trace_attrs("clear_all")
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
@limiter.limit("60/minute")
async def get_cache_stats(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Get cache statistics from Redis
    
    Returns:
        {
            "total_entries": int,
            "estimated_size_mb": float,
            "oldest_ttl_seconds": int,
            "newest_ttl_seconds": int,
            "cache_expiry_minutes": int,
            "cache_expiry_seconds": int
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
        
        # Get cache expiry in minutes for display
        from src.core.constants import CACHE_EXPIRY_MINUTES
        
        return {
            "status": "success",
            "total_entries": total_entries,
            "estimated_size_mb": round(estimated_total_size / (1024 * 1024), 2),
            "oldest_ttl_seconds": oldest_ttl,
            "newest_ttl_seconds": newest_ttl,
            "cache_expiry_minutes": CACHE_EXPIRY_MINUTES,
            "cache_expiry_seconds": CACHE_EXPIRY_MINUTES * 60
        }
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache stats: {str(e)}"
        )


@router.get("/cache/memory")
@limiter.limit("30/minute")
@observe(name="cache_memory")
async def get_redis_memory(
    request: Request,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Get actual Redis memory usage (not just cache)
    
    This shows the REAL memory usage in Redis, including:
    - Cache entries
    - ARQ job queue
    - Job results
    - Progress tracking
    - All other Redis data
    
    Returns:
        {
            "used_memory_mb": float,
            "used_memory_human": str,
            "max_memory_mb": float,
            "max_memory_human": str,
            "memory_usage_percent": float,
            "memory_available_mb": float,
            "status": "ok" | "warning" | "critical"
        }
    """
    try:
        _cache_trace_attrs("memory")
        redis_pool = await get_shared_redis_pool()
        
        # Get Redis memory info
        info = await redis_pool.info('memory')
        
        used_memory = info.get('used_memory', 0)  # Bytes
        used_memory_mb = used_memory / (1024 * 1024)
        used_memory_human = info.get('used_memory_human', f"{used_memory_mb:.2f}M")
        
        max_memory = info.get('maxmemory', 0)  # Bytes, 0 = no limit
        max_memory_mb = max_memory / (1024 * 1024) if max_memory > 0 else 30  # Default 30MB for free tier
        max_memory_human = info.get('maxmemory_human', f"{max_memory_mb:.2f}M") if max_memory > 0 else "30M"
        
        # Calculate usage percentage
        memory_usage_percent = (used_memory_mb / max_memory_mb * 100) if max_memory_mb > 0 else 0
        memory_available_mb = max_memory_mb - used_memory_mb if max_memory > 0 else None
        
        # Determine status
        if memory_usage_percent >= 90:
            status = "critical"
        elif memory_usage_percent >= 80:
            status = "warning"
        else:
            status = "ok"
        
        return {
            "status": "success",
            "used_memory_mb": round(used_memory_mb, 2),
            "used_memory_human": used_memory_human,
            "max_memory_mb": round(max_memory_mb, 2),
            "max_memory_human": max_memory_human,
            "memory_usage_percent": round(memory_usage_percent, 2),
            "memory_available_mb": round(memory_available_mb, 2) if memory_available_mb is not None else None,
            "redis_status": status,
            "message": f"Redis using {used_memory_mb:.2f}MB / {max_memory_mb:.2f}MB ({memory_usage_percent:.1f}%)"
        }
    except Exception as e:
        logger.error(f"Failed to get Redis memory: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get Redis memory: {str(e)}"
        )


@router.get("/cache/{cache_id}")
@limiter.limit("60/minute")
@observe(name="cache_get_status")
async def get_cache_status(
    request: Request,
    cache_id: str,
    api_key: str = Depends(require_api_key),
) -> Dict[str, Any]:
    """
    Check if cache exists and get its status
    
    Args:
        cache_id: Cache ID to check
        
    Returns:
        {
            "status": "exists" | "not_found" | "expired",
            "cache_id": str,
            "cache_info": {
                "cache_id": str,
                "created_at": str,
                "status": str,
                "expires_at": str,
                "ttl_seconds": int,
                "is_expired": bool
            } | null,
            "message": str
        }
    """
    try:
        _cache_trace_attrs("get_status", cache_id=cache_id[:100])
        cache_info = await agent_cache.get_cache_info(cache_id)
        
        if cache_info is None:
            return {
                "status": "not_found",
                "cache_id": cache_id,
                "cache_info": None,
                "message": f"Cache {cache_id} not found or already deleted"
            }
        
        if cache_info.get("is_expired", False):
            return {
                "status": "expired",
                "cache_id": cache_id,
                "cache_info": cache_info,
                "message": f"Cache {cache_id} has expired"
            }
        
        return {
            "status": "exists",
            "cache_id": cache_id,
            "cache_info": cache_info,
            "message": f"Cache {cache_id} exists and is valid"
        }
    except Exception as e:
        logger.error(f"Failed to get cache status {cache_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache status: {str(e)}"
        )


@router.delete("/cache/{cache_id}")
@limiter.limit("10/minute")
@observe(name="cache_delete")
async def delete_specific_cache(
    request: Request,
    cache_id: str,
    api_key: str = Depends(require_api_key),
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
        _cache_trace_attrs("delete", cache_id=cache_id[:100])
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

