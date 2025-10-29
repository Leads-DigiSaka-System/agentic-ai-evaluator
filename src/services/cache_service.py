import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class AgentOutputCache:
    """
    Cache service for agent output with automatic cleanup
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self.cache_expiry_hours = 24  # Cache expires after 24 hours
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        logger.info(f"📦 AgentOutputCache initialized with directory: {self.cache_dir}")
    
    def _get_cache_file_path(self, cache_id: str) -> str:
        """Get cache file path for a given cache ID"""
        return os.path.join(self.cache_dir, f"{cache_id}.json")
    
    def _is_cache_expired(self, cache_data: Dict[str, Any]) -> bool:
        """Check if cache data is expired"""
        try:
            created_at = datetime.fromisoformat(cache_data.get("created_at", ""))
            expiry_time = created_at + timedelta(hours=self.cache_expiry_hours)
            return datetime.now() > expiry_time
        except:
            return True  # If we can't parse the date, consider it expired
    
    def save_agent_output(self, agent_response: Dict[str, Any]) -> str:
        """
        Save agent output to cache and return cache ID
        
        Args:
            agent_response: Response from /api/agent endpoint
            
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
            
            # Save to file
            cache_file_path = self._get_cache_file_path(cache_id)
            with open(cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Agent output cached with ID: {cache_id}")
            
            # Add cache_id to agent response for frontend
            agent_response["cache_id"] = cache_id
            
            return cache_id
            
        except Exception as e:
            logger.error(f"Failed to cache agent output: {str(e)}")
            raise Exception(f"Cache save failed: {str(e)}")
    
    def get_cached_output(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached agent output
        
        Args:
            cache_id: Cache identifier
            
        Returns:
            Cached agent response or None if not found/expired
        """
        try:
            cache_file_path = self._get_cache_file_path(cache_id)
            
            if not os.path.exists(cache_file_path):
                logger.warning(f"Cache file not found: {cache_id}")
                return None
            
            # Load cache data
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if expired
            if self._is_cache_expired(cache_data):
                logger.info(f"Cache expired, deleting: {cache_id}")
                self.delete_cache(cache_id)
                return None
            
            logger.info(f"Retrieved cached output: {cache_id}")
            return cache_data.get("agent_response")
            
        except Exception as e:
            logger.error(f"Failed to retrieve cache {cache_id}: {str(e)}")
            return None
    
    def delete_cache(self, cache_id: str) -> bool:
        """
        Delete cached data
        
        Args:
            cache_id: Cache identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            cache_file_path = self._get_cache_file_path(cache_id)
            
            if os.path.exists(cache_file_path):
                os.remove(cache_file_path)
                logger.info(f"Cache deleted: {cache_id}")
                return True
            else:
                logger.warning(f"Cache file not found for deletion: {cache_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete cache {cache_id}: {str(e)}")
            return False
    
    def cleanup_expired_caches(self) -> int:
        """
        Clean up all expired cache files
        
        Returns:
            Number of files cleaned up
        """
        try:
            cleaned_count = 0
            
            if not os.path.exists(self.cache_dir):
                return 0
            
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    cache_id = filename[:-5]  # Remove .json extension
                    
                    try:
                        cache_file_path = os.path.join(self.cache_dir, filename)
                        with open(cache_file_path, 'r', encoding='utf-8') as f:
                            cache_data = json.load(f)
                        
                        if self._is_cache_expired(cache_data):
                            os.remove(cache_file_path)
                            cleaned_count += 1
                            logger.info(f"Cleaned expired cache: {cache_id}")
                            
                    except Exception as e:
                        logger.warning(f"Error processing cache file {filename}: {str(e)}")
                        # Remove corrupted files
                        try:
                            os.remove(os.path.join(self.cache_dir, filename))
                            cleaned_count += 1
                        except:
                            pass
            
            logger.info(f"Cleanup completed: {cleaned_count} expired caches removed")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")
            return 0
    
    def get_cache_info(self, cache_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cache metadata without loading full data
        
        Args:
            cache_id: Cache identifier
            
        Returns:
            Cache metadata or None if not found
        """
        try:
            cache_file_path = self._get_cache_file_path(cache_id)
            
            if not os.path.exists(cache_file_path):
                return None
            
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Return metadata only
            return {
                "cache_id": cache_data.get("cache_id"),
                "created_at": cache_data.get("created_at"),
                "status": cache_data.get("status"),
                "expires_at": (
                    datetime.fromisoformat(cache_data.get("created_at", "")) + 
                    timedelta(hours=self.cache_expiry_hours)
                ).isoformat(),
                "is_expired": self._is_cache_expired(cache_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache info {cache_id}: {str(e)}")
            return None


# Global cache instance
agent_cache = AgentOutputCache()
