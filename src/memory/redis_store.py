import json
import logging
from typing import Any, Dict, List, Optional
import redis

from src.utils.config import config

logger = logging.getLogger(__name__)

class RedisMemoryStore:
    """Advanced Redis memory store for fast, multi-process synchronization."""
    
    def __init__(self):
        try:
            self.client = redis.Redis.from_url(
                config.settings.redis_url, 
                decode_responses=True
            )
            # Ping to check connection
            self.client.ping()
            logger.info("Connected to Redis successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def is_connected(self) -> bool:
        return self.client is not None

    def cache_session_state(self, session_id: str, state: Dict[str, Any], expire_seconds: int = 3600):
        """Cache active session state (e.g. loaded context, temporary flags) for quick access."""
        if not self.is_connected():
            return
        
        try:
            key = f"session:{session_id}:state"
            self.client.setex(key, expire_seconds, json.dumps(state))
        except Exception as e:
            logger.error(f"Error caching session state in Redis: {e}")

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve active session state."""
        if not self.is_connected():
            return None
        
        try:
            key = f"session:{session_id}:state"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting session state from Redis: {e}")
            return None

    def publish_event(self, channel: str, event_data: Dict[str, Any]):
        """Publish an event to a Redis channel for multi-process sync."""
        if not self.is_connected():
            return
            
        try:
            self.client.publish(channel, json.dumps(event_data))
        except Exception as e:
            logger.error(f"Error publishing to Redis channel {channel}: {e}")

    def set_active_model(self, session_id: str, model_id: str, expire_seconds: int = 3600):
        """Quickly store the currently active model for a session."""
        if not self.is_connected():
            return
            
        try:
            key = f"session:{session_id}:active_model"
            self.client.setex(key, expire_seconds, model_id)
        except Exception as e:
            logger.error(f"Error setting active model in Redis: {e}")

    def get_active_model(self, session_id: str) -> Optional[str]:
        """Get the currently active model for a session."""
        if not self.is_connected():
            return None
            
        try:
            key = f"session:{session_id}:active_model"
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Error getting active model from Redis: {e}")
            return None

    def clear_session_cache(self, session_id: str):
        """Clear all cached data for a given session."""
        if not self.is_connected():
            return
            
        try:
            keys = self.client.keys(f"session:{session_id}:*")
            if keys:
                self.client.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing session cache in Redis: {e}")

# Global instance
redis_store = RedisMemoryStore()
