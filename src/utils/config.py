import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── OpenRouter API ───────────────────────────────────────
    openrouter_api_key: str = Field(..., description="OpenRouter API key")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # ── Model configuration ───────────────────────────────────
    model_qwen: str = "qwen/qwen3.5-flash-02-23"
    model_gemini_flash: str = "google/gemini-2.5-flash-lite"
    model_mimo: str = "xiaomi/mimo-v2.5-pro"
    model_deepseek_flash: str = "deepseek/deepseek-v4-flash"
    model_deepseek_pro: str = "deepseek/deepseek-v4-pro"
    model_summary: str = "openai/gpt-oss-120b"
    
    # ── Model Costs ──────────────────────────────────────────
    model_qwen_cost_input: float = 0.065
    model_qwen_cost_output: float = 0.26
    model_gemini_flash_cost_input: float = 0.10
    model_gemini_flash_cost_output: float = 0.40
    model_mimo_cost_input: float = 1.0
    model_mimo_cost_output: float = 3.0
    model_deepseek_flash_cost_input: float = 0.14
    model_deepseek_flash_cost_output: float = 0.28
    model_deepseek_pro_cost_input: float = 0.435
    model_deepseek_pro_cost_output: float = 0.87
    model_summary_cost_input: float = 0.0
    model_summary_cost_output: float = 0.0

    # ── Memory configuration ─────────────────────────────────
    sqlite_db_path: str = "data/sqlite/memory.db"
    chroma_db_path: str = "data/chroma"
    documents_path: str = "data/documents"
    redis_url: str = "redis://localhost:6379/0"

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
    model_costs: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    # ── Intelligent Routing & Capabilities ───────────────────────
    model_capabilities: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    complexity_routing: Dict[str, str] = Field(default_factory=dict)
    
    # ── Chat enhancements ─────────────────────────────────────
    default_chat_model: str = ""
    system_prompt: str = "Your name is Mira, an intelligent Orchestrator AI. You have access to expert sub-agents via the `ask_expert_model` tool. You also have a long-term memory system. When provided with memory snippets, you MUST use them and acknowledge them." # IMPORTANT: DeepSeek is highly capable of general logic, prompt engineering, and complex writing—it is NOT just for coding. Do not force it to write code unless the user explicitly asks for code. Use Mimo-v2.5 for complex reasoning, especially when the user provides multimodal inputs (Images, Audio, Video).
    summary_max_tokens: int = 400
    tag_extraction_model: Optional[str] = None

    # -----------------------------------------------------------------
    # Pydantic v2 configuration – replaces the old `class Config`
    # -----------------------------------------------------------------
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def populate_model_dicts(self) -> "Settings":
        # Populate model costs
        self.model_costs = {
            self.model_qwen: {"input": self.model_qwen_cost_input, "output": self.model_qwen_cost_output},
            self.model_gemini_flash: {"input": self.model_gemini_flash_cost_input, "output": self.model_gemini_flash_cost_output},
            self.model_mimo: {"input": self.model_mimo_cost_input, "output": self.model_mimo_cost_output},
            self.model_deepseek_flash: {"input": self.model_deepseek_flash_cost_input, "output": self.model_deepseek_flash_cost_output},
            self.model_deepseek_pro: {"input": self.model_deepseek_pro_cost_input, "output": self.model_deepseek_pro_cost_output},
            self.model_summary: {"input": self.model_summary_cost_input, "output": self.model_summary_cost_output},
        }

        # Populate capabilities
        self.model_capabilities = {
            self.model_qwen: {
                "role": "default_orchestrator",
                "supports": {"text": True, "image": True, "video": True, "audio": False, "multimodal_reasoning": True, "tool_use": True, "long_context": True},
                "strengths": ["fast_chat", "videos", "multimodal_parsing", "conversation", "intent_classification", "tool_routing", "lightweight_coding", "memory_handling"],
                "best_use_cases": ["general_chat", "screenshots", "videos", "small_video_analysis", "lightweight_debugging", "tool_orchestration", "routing", "OCR", "quick_multimodal_tasks"],
                "reasoning_level": 6, "coding_level": 6, "planning_level": 5,
            },
            self.model_gemini_flash: {
                "role": "efficient_multimodal_processor",
                "supports": {"text": True, "image": True, "video": True, "audio": True, "multimodal_reasoning": True, "tool_use": True, "long_context": True},
                "strengths": ["OCR", "large_pdf_analysis", "video_understanding", "long_context_processing", "multimodal_extraction", "high_throughput_processing"],
                "best_use_cases": ["large_documents", "research_extraction", "video_analysis", "audio_transcription", "long_transcripts", "memory_synthesis", "high_volume_multimodal"],
                "reasoning_level": 7, "coding_level": 6, "planning_level": 6,
            },
            self.model_deepseek_pro: {
                "role": "agentic_reasoning_engine",
                "supports": {"text": True, "image": False, "video": False, "audio": False, "multimodal_reasoning": False, "tool_use": True, "long_context": True},
                "strengths": ["deep_reasoning", "analysis", "agentic_reasoning", "planning", "decomposition", "workflow_design", "autonomous_reasoning", "architecture_generation", "multi_step_reasoning", "maths"],
                "best_use_cases": ["deep_reasoning", "analysis", "AI_agents", "workflow_planning", "autonomous_systems", "multi_agent_systems", "architecture_design", "research_decomposition", "strategic_reasoning"],
                "reasoning_level": 9, "coding_level": 10, "planning_level": 10,
            },
            self.model_deepseek_flash: {
                "role": "software_engineering_specialist",
                "supports": {"text": True, "image": False, "video": False, "audio": False, "multimodal_reasoning": False, "tool_use": True, "long_context": True},
                "strengths": ["coding", "debugging", "reasoning", "repository_reasoning", "algorithms", "backend_architecture", "optimization", "refactoring", "devops"],
                "best_use_cases": ["coding", "reasoning", "backend_systems", "large_codebases", "APIs", "infrastructure", "AI_pipelines", "database_optimization", "production_engineering"],
                "reasoning_level": 8, "coding_level": 9.5, "planning_level": 7,
            },
            self.model_mimo: {
                "role": "maximum_intelligence_engine",
                "supports": {"text": True, "image": False, "video": False, "audio": False, "multimodal_reasoning": False, "tool_use": True, "long_context": True},
                "strengths": ["very_deep_reasoning", "massive_synthesis", "research", "cross_document_analysis", "scientific_reasoning", "enterprise_reasoning", "highest_reliability"],
                "best_use_cases": ["research_systems", "massive_documents", "enterprise_analysis", "scientific_workflows", "high_stakes_outputs", "cross_modal_reasoning", "large_scale_synthesis"],
                "reasoning_level": 10, "coding_level": 9, "planning_level": 9,
            },
        }

        # Populate complexity routing
        self.complexity_routing = {
            "0-3": self.model_qwen,
            "4-6": self.model_gemini_flash,
            "7-10": self.model_deepseek_flash,
            "11-12": self.model_deepseek_pro,
            "13+": self.model_mimo,
        }
        
        if not self.default_chat_model:
            self.default_chat_model = self.model_qwen
            
        return self

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
            "qwen-2.5-32b-instruct": self.settings.model_qwen,
            "gemini-2.5-flash-lite": self.settings.model_gemini_flash,
            "mimo-v2.5-pro": self.settings.model_mimo,
            "deepseek-v4-flash": self.settings.model_deepseek_flash,
            "deepseek-v4-pro": self.settings.model_deepseek_pro,
            "gpt-oss-120b": self.settings.model_summary,
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