import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Callable
import redis

from src.utils.config import config

logger = logging.getLogger(__name__)

class RedisMemoryStore:
    """Advanced Redis memory store for fast, multi-process synchronization."""
    
    def __init__(self):
        self.client = None
        self.pubsub = None
        self._listener_thread = None
        self._redis_process = None  # Tracks the auto-started Redis subprocess
        self.connect()

    def _try_auto_start_redis(self) -> bool:
        """
        Attempt to automatically start Redis.
        Priority:
          1. Bundled portable redis-server.exe (bin/redis/redis-server.exe) inside the project.
          2. Native system-wide installation (PATH / common Windows dirs).
        Tracks the spawned process and registers an atexit hook to shut it down on quit.
        """
        import atexit
        from pathlib import Path

        # Locate project root (this file is at src/memory/redis_store.py)
        project_root = Path(__file__).resolve().parents[2]
        bundled = project_root / "bin" / "redis" / "redis-server.exe"

        candidates = [
            str(bundled),
            shutil.which("redis-server"),
            shutil.which("memurai"),
            r"C:\Program Files\Redis\redis-server.exe",
            r"C:\Program Files\Memurai\memurai.exe",
            r"C:\Redis\redis-server.exe",
        ]

        redis_bin = next((c for c in candidates if c and os.path.exists(c)), None)

        if not redis_bin:
            msg = "INFO: No Redis executable found (bundled or system). Falling back to SQLite."
            logger.info(msg)
            print(msg, file=sys.stderr, flush=True)
            return False

        try:
            label = "bundled" if str(bundled) == redis_bin else "system"
            msg = f"INFO: Auto-starting {label} Redis from {redis_bin}..."
            logger.info(msg)
            print(msg, file=sys.stderr, flush=True)

            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            data_dir = project_root / "data" / "redis"
            data_dir.mkdir(parents=True, exist_ok=True)
            proc = subprocess.Popen(
                [redis_bin, "--port", "6379", "--loglevel", "warning",
                 "--dir", str(project_root / "data" / "redis"),
                 "--dbfilename", "dump.rdb"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            self._redis_process = proc

            # Register shutdown hook: terminate Redis when Python process exits
            def _shutdown_redis():
                try:
                    if proc.poll() is None:
                        print("INFO: Shutting down bundled Redis server...", file=sys.stderr, flush=True)
                        proc.terminate()
                        proc.wait(timeout=5)
                        print("INFO: Redis server stopped.", file=sys.stderr, flush=True)
                except Exception as e:
                    logger.debug(f"Redis shutdown error: {e}")

            atexit.register(_shutdown_redis)

            # Wait for Redis to be ready (retry up to 5s)
            for _ in range(10):
                time.sleep(0.5)
                try:
                    import redis as _redis
                    test_client = _redis.Redis(host="localhost", port=6379, socket_timeout=1.0, protocol=2)
                    test_client.ping()
                    break  # Ready!
                except Exception:
                    continue
            return True

        except Exception as err:
            logger.debug(f"Redis auto-start error: {err}")
            return False


    def connect(self) -> bool:
        """Attempt to connect or reconnect to Redis with auto-start capability."""
        url = getattr(config.settings, 'redis_url', 'redis://localhost:6379/0')
        
        # Try initial connection
        try:
            self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2.0, protocol=2)
            self.client.ping()
            msg = "INFO: Connected to Redis memory store successfully."
            logger.info(msg)
            print(msg, file=sys.stderr, flush=True)
            return True
        except Exception:
            pass

        # Try auto-starting Redis
        if self._try_auto_start_redis():
            try:
                self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=2.0, protocol=2)
                self.client.ping()
                msg = "INFO: Connected to Redis memory store after auto-start."
                logger.info(msg)
                print(msg, file=sys.stderr, flush=True)
                return True
            except Exception as e:
                msg = f"WARNING: Redis auto-start completed, but ping failed (falling back to SQLite): {e}"
                logger.warning(msg)
                print(msg, file=sys.stderr, flush=True)

        msg = "INFO: Redis connection unavailable (falling back to SQLite)."
        logger.info(msg)
        print(msg, file=sys.stderr, flush=True)
        self.client = None
        return False

    def is_connected(self) -> bool:
        """Check if Redis connection is active."""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            self.client = None
            return False

    # -------------------------------------------------------------------------
    # Session State & Model Caching
    # -------------------------------------------------------------------------
    def cache_session_state(self, session_id: str, state: Dict[str, Any], expire_seconds: int = 3600):
        """Cache active session state for quick access across processes."""
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

    # -------------------------------------------------------------------------
    # Context Assembly Caching
    # -------------------------------------------------------------------------
    def cache_assembled_context(self, session_id: str, context_data: Dict[str, Any], expire_seconds: int = 300):
        """Cache assembled context to avoid rebuilding on rapid multi-turn requests."""
        if not self.is_connected():
            return
        try:
            key = f"session:{session_id}:context"
            self.client.setex(key, expire_seconds, json.dumps(context_data))
        except Exception as e:
            logger.error(f"Error caching assembled context in Redis: {e}")

    def get_assembled_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached assembled context if fresh."""
        if not self.is_connected():
            return None
        try:
            key = f"session:{session_id}:context"
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error getting assembled context from Redis: {e}")
            return None

    # -------------------------------------------------------------------------
    # Concurrency & Distributed Lock
    # -------------------------------------------------------------------------
    def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """Acquire a distributed lock to prevent race conditions across processes."""
        if not self.is_connected():
            return True  # Fallback to single-process behavior
        try:
            key = f"lock:{lock_name}"
            return bool(self.client.set(key, "locked", nx=True, ex=timeout))
        except Exception as e:
            logger.error(f"Error acquiring lock {lock_name}: {e}")
            return True

    def release_lock(self, lock_name: str):
        """Release a distributed lock."""
        if not self.is_connected():
            return
        try:
            key = f"lock:{lock_name}"
            self.client.delete(key)
        except Exception as e:
            logger.error(f"Error releasing lock {lock_name}: {e}")

    # -------------------------------------------------------------------------
    # Multi-Process Pub/Sub Broadcasting
    # -------------------------------------------------------------------------
    def publish_event(self, channel: str, event_data: Dict[str, Any]):
        """Publish an event to a Redis channel for multi-process sync."""
        if not self.is_connected():
            return
            
        try:
            self.client.publish(channel, json.dumps(event_data))
        except Exception as e:
            logger.error(f"Error publishing to Redis channel {channel}: {e}")

    def publish_message(self, session_id: str, role: str, content: str, model_id: Optional[str] = None):
        """Publish a new chat message event to all listening processes (UI, CLI, Daemon)."""
        event = {
            "type": "message",
            "session_id": session_id,
            "role": role,
            "content": content,
            "model_id": model_id,
            "timestamp": time.time()
        }
        self.publish_event("agenticai:chat_events", event)

    def subscribe_events(self, callback: Callable[[Dict[str, Any]], None], channel: str = "agenticai:chat_events"):
        """Subscribe to a Redis channel in a background thread and invoke callback on events."""
        if not self.is_connected():
            return

        def _listen():
            try:
                pubsub = self.client.pubsub()
                pubsub.subscribe(channel)
                for message in pubsub.listen():
                    if message and message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            callback(data)
                        except Exception as e:
                            logger.error(f"Error parsing pubsub message: {e}")
            except Exception as e:
                logger.error(f"Redis pubsub thread error: {e}")

        self._listener_thread = threading.Thread(target=_listen, daemon=True)
        self._listener_thread.start()

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

