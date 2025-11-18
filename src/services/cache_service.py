import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging
from src.generator.redis_pool import get_shared_redis_pool
logger = logging.getLogger(__name__)

class AgentOutputCache:
    """
    Cache service for agent output with automatic cleanup
    """
    
    def __init__(self, redis_url: str = None):
        from src.utils.constants import CACHE_EXPIRY_HOURS, CACHE_EXPIRY_SECONDS
        self.cache_expiry_hours = CACHE_EXPIRY_HOURS
        self.cache_expiry_seconds = CACHE_EXPIRY_SECONDS
        logger.info(f"AgentOutputCache initialized (using shared Redis pool)")
    
    def _get_cache_key(self, cache_id: str, user_id: Optional[str] = None) -> str:
        """Get Redis key for a given cache ID, optionally scoped to user"""
        if user_id:
            return f"agent:cache:{user_id}:{cache_id}"
        return f"agent:cache:{cache_id}"
    
    async def _get_redis_pool(self):
        """
        Get shared Redis connection pool
        
        Uses the shared pool manager to avoid creating multiple connections.
        This improves performance by reusing a single connection pool.
        """
        return await get_shared_redis_pool()
    
    def _is_cache_expired(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cache data is expired"""
        try:
            created_at = datetime.fromisoformat(cache_data.get("created_at", ""))
            expiry_time = created_at + timedelta(hours=self.cache_expiry_hours)
            return datetime.now() > expiry_time
        except:
            return True  # If we can't parse the date, consider it expired
    
    async def save_agent_output(self, agent_response: Dict[str, Any], session_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
        """
        Save agent output to cache and return cache ID
        
        Args:
            agent_response: Response from /api/agent endpoint
            session_id: Optional session ID to link storage approval to original session
            user_id: Optional user ID for data isolation
            
        Returns:
            cache_id: Unique identifier for retrieving cached data
        """
        try:
            # Generate unique cache ID
            cache_id = str(uuid.uuid4())
            
            # Prepare cache data
            cache_data = {
                "cache_id": cache_id,
                "created_at": datetime.now().isoformat(),
                "agent_response": agent_response,
                "status": "pending_storage"
            }
            
            # Store session_id if provided (for linking storage approval to original session)
            if session_id:
                cache_data["session_id"] = session_id
            
            # Store user_id if provided (for user data isolation)
            if user_id:
                cache_data["user_id"] = user_id

            redis_pool = await self._get_redis_pool()
            
            # Save to Redis (with user-scoped key if user_id provided)
            cache_key = self._get_cache_key(cache_id, user_id)
            await redis_pool.setex(
                cache_key,
                self.cache_expiry_seconds,
                json.dumps(cache_data, ensure_ascii=False)
            )

            
            logger.info(f"Agent output cached with ID: {cache_id}")
            
            # Add cache_id to agent response for frontend
            agent_response["cache_id"] = cache_id
            
            return cache_id
            
        except Exception as e:
            logger.error(f"Failed to cache agent output: {str(e)}")
            raise Exception(f"Cache save failed: {str(e)}")
    
    async def get_cached_output(self, cache_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached agent output
        
        Args:
            cache_id: Cache identifier
            user_id: Optional user ID for data isolation (must match if cache was saved with user_id)
            
        Returns:
            Cached agent response or None if not found/expired
        """
        try:
            redis_pool = await self._get_redis_pool()

            # Try user-scoped key first if user_id provided
            cache_key = self._get_cache_key(cache_id, user_id)
            cache_data_raw = await redis_pool.get(cache_key)
            
            # If not found and user_id provided, try without user_id (backward compatibility)
            if not cache_data_raw and user_id:
                cache_key = self._get_cache_key(cache_id)
                cache_data_raw = await redis_pool.get(cache_key)
            if not cache_data_raw:
                logger.warning(f"Cache not found: {cache_id}")
                return None
            
            # Decode if bytes
            if isinstance(cache_data_raw, bytes):
                cache_data_raw = cache_data_raw.decode()
            
            cache_data = json.loads(cache_data_raw)
            
            if self._is_cache_expired(cache_data):
                logger.info(f"Cache expired, deleting: {cache_id}")
                await redis_pool.delete(cache_key)
                return None
            
            logger.info(f"Retrieved cached output: {cache_id}")
            # Return the full cache_data so we can access session_id and other metadata
            return cache_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cache data {cache_id}: {str(e)}")
            # Delete corrupted cache
            try:
                redis_pool = await self._get_redis_pool()
                cache_key = self._get_cache_key(cache_id)
                await redis_pool.delete(cache_key)
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve cache {cache_id}: {str(e)}")
            return None
    
    async def delete_cache(self, cache_id: str) -> bool:
        """
        Delete cached data
        
        Args:
            cache_id: Cache identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            redis_pool = await self._get_redis_pool()
            cache_key = self._get_cache_key(cache_id)
            
            deleted = await redis_pool.delete(cache_key)

            if deleted:
                return True
            else:
                logger.warning(f"Cache not found for deletion: {cache_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete cache {cache_id}: {str(e)}")
            return False
    
    async def cleanup_expired_caches(self) -> int:
        """
        Clean up all expired cache entries from Redis
        Note: Redis TTL handles expiration automatically, but this can scan for any missed entries
        
        Returns:
            Number of entries cleaned up
        """
        try:
            redis_pool = await self._get_redis_pool()
            cache_keys = await redis_pool.keys("agent:cache:*")
            cleaned_count = 0
            
            for cache_key in cache_keys:
                # Decode key if bytes
                if isinstance(cache_key, bytes):
                    cache_key = cache_key.decode()
                
                cache_data_raw = await redis_pool.get(cache_key)
                if not cache_data_raw:
                    continue
                
                # Decode if bytes
                if isinstance(cache_data_raw, bytes):
                    cache_data_raw = cache_data_raw.decode()
                
                try:
                    cache_data = json.loads(cache_data_raw)
                except json.JSONDecodeError:
                    # Delete corrupted cache
                    await redis_pool.delete(cache_key)
                    cleaned_count += 1
                    continue
                    
                if self._is_cache_expired(cache_data):
                    await redis_pool.delete(cache_key)
                    cleaned_count += 1
                    cache_id = cache_data.get("cache_id", "unknown")
                    logger.info(f"Cleaned expired cache: {cache_id}")
            
            logger.info(f"Cleanup completed: {cleaned_count} expired caches removed")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")
            return 0
    
    async def get_cache_info(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cache metadata without loading full data
        
        Args:
            cache_id: Cache identifier
            
        Returns:
            Cache metadata or None if not found
        """
        try:
            redis_pool = await self._get_redis_pool()
            cache_key = self._get_cache_key(cache_id)
            
            # Get TTL from Redis
            ttl = await redis_pool.ttl(cache_key)
            if ttl == -2:  # Key doesn't exist
                return None
            
            cache_data_raw = await redis_pool.get(cache_key)
            if not cache_data_raw:
                return None
            
            # Decode if bytes
            if isinstance(cache_data_raw, bytes):
                cache_data_raw = cache_data_raw.decode()
            
            cache_data = json.loads(cache_data_raw)
            
            # Calculate expiry time
            created_at = datetime.fromisoformat(cache_data.get("created_at", ""))
            expires_at = created_at + timedelta(hours=self.cache_expiry_hours)
            
            # Return metadata only
            return {
                "cache_id": cache_data.get("cache_id"),
                "created_at": cache_data.get("created_at"),
                "status": cache_data.get("status"),
                "expires_at": expires_at.isoformat(),
                "ttl_seconds": ttl if ttl > 0 else 0,
                "is_expired": self._is_cache_expired(cache_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache info {cache_id}: {str(e)}")
            return None
    


# Global cache instance
agent_cache = AgentOutputCache()
