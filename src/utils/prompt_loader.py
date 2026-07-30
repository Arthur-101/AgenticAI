import os
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

class PromptLoader:
    """Startup-cached loader for system instructions stored in data/prompts/*.txt."""
    
    PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "prompts"
    _cache: Dict[str, str] = {}
    _initialized: bool = False

    @classmethod
    def _initialize_cache(cls):
        """Read all .txt prompt files in data/prompts into memory once at startup."""
        if cls._initialized and cls._cache:
            return

        cls.PROMPT_DIR.mkdir(parents=True, exist_ok=True)
        cls._cache.clear()

        try:
            for file_path in cls.PROMPT_DIR.glob("*.txt"):
                prompt_name = file_path.stem.lower()
                try:
                    content = file_path.read_text(encoding="utf-8").strip()
                    cls._cache[prompt_name] = content
                    logger.debug(f"Loaded prompt template [{prompt_name}] into memory cache.")
                except Exception as e:
                    logger.error(f"Failed to read prompt file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error accessing prompt directory {cls.PROMPT_DIR}: {e}")

        cls._initialized = True

    @classmethod
    def get_prompt(cls, prompt_name: str, fallback_text: str = "") -> str:
        """Fetch prompt template from memory cache (cached at startup)."""
        if not cls._initialized:
            cls._initialize_cache()

        clean_name = prompt_name.lower().replace(".txt", "")
        if clean_name in cls._cache and cls._cache[clean_name]:
            return cls._cache[clean_name]

        # If missing from cache, try reading file directly
        file_path = cls.PROMPT_DIR / f"{clean_name}.txt"
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8").strip()
                cls._cache[clean_name] = content
                return content
            except Exception:
                pass

        # If fallback text provided, auto-create file for convenience
        if fallback_text:
            try:
                cls.PROMPT_DIR.mkdir(parents=True, exist_ok=True)
                file_path.write_text(fallback_text.strip(), encoding="utf-8")
                cls._cache[clean_name] = fallback_text.strip()
            except Exception as e:
                logger.error(f"Failed to write fallback prompt {clean_name}: {e}")

        return fallback_text.strip()

    @classmethod
    def reload_cache(cls):
        """Force reload prompt files into memory (e.g. on app restart)."""
        cls._initialized = False
        cls._initialize_cache()


# Pre-initialize cache when module is imported
PromptLoader._initialize_cache()
