import os
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── OpenRouter API ───────────────────────────────────────
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # ── Model configuration ───────────────────────────────────
    model_qwen: str = "qwen/qwen-2.5-32b-instruct"
    model_gemini_flash: str = "google/gemini-2.5-flash-lite"
    model_mimo: str = "mimo/mimo-v2-pro"
    model_deepseek: str = "deepseek/deepseek-v3.2"
    model_gemini_pro: str = "google/gemini-3.1-pro"

    # ── Memory configuration ─────────────────────────────────
    sqlite_db_path: str = "data/sqlite/memory.db"
    chroma_db_path: str = "data/chroma"
    documents_path: str = "data/documents"

    # ── Cost tracking ────────────────────────────────────────
    cost_warning_threshold: float = 10.0
    cost_limit: float = 50.0

    # ── Security settings ────────────────────────────────────
    allowed_file_types: List[str] = [
        ".py",
        ".pdf",
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
    ]
    max_file_size_mb: int = 10
    require_permission_prompt: bool = True

    # ── Performance settings ─────────────────────────────────
    max_tokens_per_request: int = 4000
    temperature: float = 0.7
    request_timeout: int = 30

    # ── Model costs (per‑million‑tokens) ───────────────────────
    model_costs: Dict[str, Dict[str, float]] = {
        "qwen/qwen-2.5-32b-instruct": {"input": 0.50, "output": 0.50},
        "google/gemini-2.5-flash-lite": {"input": 0.10, "output": 0.30},
        "mimo/mimo-v2-pro": {"input": 1.50, "output": 4.50},
        "deepseek/deepseek-v3.2": {"input": 0.14, "output": 0.28},
        "google/gemini-3.1-pro": {"input": 1.25, "output": 5.00},
    }

    # ── Task‑type → model mapping (initial rule set) ───────────
    task_model_mapping: Dict[str, str] = {
        "simple_chat": "gemini-2.5-flash-lite",
        "coding": "deepseek-v3.2",
        "complex_reasoning": "mimo-v2-pro",
        "multimodal": "gemini-3.1-pro",
        "default": "qwen-2.5-32b-instruct",
    }

    # -----------------------------------------------------------------
    # Pydantic v2 configuration – replaces the old `class Config`
    # -----------------------------------------------------------------
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    # -----------------------------------------------------------------
    # Validators (v2, mode="before" – run before JSON decoding)
    # -----------------------------------------------------------------
    @field_validator("sqlite_db_path", "chroma_db_path", "documents_path", mode="before")
    @classmethod
    def _ensure_parent_dirs(cls, v: str) -> str:
        """Create parent directories for any path‑like setting."""
        path = Path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @field_validator("allowed_file_types", mode="before")
    @classmethod
    def _parse_file_types(cls, v: Any) -> List[str]:
        """Accept a comma‑separated string from .env or a JSON array."""
        import json
        if isinstance(v, str):
            # Try to parse as JSON first (for JSON arrays)
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                # If not JSON, treat as comma-separated string
                return [ft.strip() for ft in v.split(",") if ft.strip()]
        return v


class ConfigManager:
    """Manages configuration and settings."""
    
    def __init__(self):
        self.settings = Settings()
        self._cost_tracker = {"total_cost": 0.0, "model_usage": {}}
        self._initialize_directories()
    
    def _initialize_directories(self):
        """Initialize all required directories."""
        directories = [
            Path(self.settings.sqlite_db_path).parent,
            Path(self.settings.chroma_db_path),
            Path(self.settings.documents_path),
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def get_model_cost(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for a model usage."""
        if model_id not in self.settings.model_costs:
            model_id = self._map_model_name(model_id)
        
        if model_id not in self.settings.model_costs:
            return 0.0
        
        cost_config = self.settings.model_costs[model_id]
        input_cost = (input_tokens / 1_000_000) * cost_config["input"]
        output_cost = (output_tokens / 1_000_000) * cost_config["output"]
        
        return input_cost + output_cost
    
    def _map_model_name(self, model_name: str) -> str:
        """Map friendly model names to OpenRouter model IDs."""
        mapping = {
            "qwen-2.5-32b-instruct": "qwen/qwen-2.5-32b-instruct",
            "gemini-2.5-flash-lite": "google/gemini-2.5-flash-lite",
            "mimo-v2-pro": "mimo/mimo-v2-pro",
            "deepseek-v3.2": "deepseek/deepseek-v3.2",
            "gemini-3.1-pro": "google/gemini-3.1-pro",
        }
        return mapping.get(model_name, model_name)
    
    def track_cost(self, model_id: str, input_tokens: int, output_tokens: int):
        """Track cost usage and check limits."""
        cost = self.get_model_cost(model_id, input_tokens, output_tokens)
        
        # Update cost tracker
        self._cost_tracker["total_cost"] += cost
        if model_id not in self._cost_tracker["model_usage"]:
            self._cost_tracker["model_usage"][model_id] = {
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        
        self._cost_tracker["model_usage"][model_id]["cost"] += cost
        self._cost_tracker["model_usage"][model_id]["input_tokens"] += input_tokens
        self._cost_tracker["model_usage"][model_id]["output_tokens"] += output_tokens
        
        # Check warnings and limits
        self._check_cost_limits()
    
    def _check_cost_limits(self):
        """Check if cost limits are exceeded and issue warnings."""
        total_cost = self._cost_tracker["total_cost"]
        
        if total_cost >= self.settings.cost_limit:
            print(f"⚠️  COST LIMIT EXCEEDED: ${total_cost:.2f} (limit: ${self.settings.cost_limit})")
        elif total_cost >= self.settings.cost_warning_threshold:
            print(f"⚠️  Cost warning: ${total_cost:.2f} (threshold: ${self.settings.cost_warning_threshold})")
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get current cost summary."""
        return {
            "total_cost": self._cost_tracker["total_cost"],
            "model_usage": self._cost_tracker["model_usage"],
            "cost_limit": self.settings.cost_limit,
            "cost_warning_threshold": self.settings.cost_warning_threshold,
        }
    
    def is_file_type_allowed(self, file_path: str) -> bool:
        """Check if file type is allowed."""
        path = Path(file_path)
        return any(path.name.lower().endswith(ft) for ft in self.settings.allowed_file_types)
    
    def is_file_size_allowed(self, file_path: str) -> bool:
        """Check if file size is within limits."""
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            return size_mb <= self.settings.max_file_size_mb
        except OSError:
            return False


# Global config instance
config = ConfigManager()