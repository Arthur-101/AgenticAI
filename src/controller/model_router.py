"""
Intelligent Task Router — role-based multi-signal routing engine.

Architecture
------------
1. TaskSignalExtractor  – extracts structured, weighted signals from the user message
2. CapabilityMatcher    – stateless heuristic that infers model capabilities from
                          provider name + model-ID pattern rules (no static registry)
3. IntelligentRouter    – resolves role→model from Redis/SQLite assignments and
                          selects the best role for the detected task type
4. Legacy shims         – ModelRouter / TaskAnalyzer kept for backwards compatibility
"""

from __future__ import annotations

import re
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Tuple

from src.models.openrouter_client import ModelType, Message, OpenRouterClient
from src.utils.config import config


# ─────────────────────────────────────────────────────────
# Enums & Data Structures
# ─────────────────────────────────────────────────────────

class TaskType(Enum):
    """High-level task type driving role selection."""
    CASUAL        = "casual"          # greetings, small-talk, very short queries
    GENERAL       = "general"         # factual Q&A, summarisation, translation
    MULTIMODAL    = "multimodal"      # attached images, video, audio references
    CODING        = "coding"          # code generation, debugging, refactoring
    REASONING     = "reasoning"       # analysis, planning, architecture, maths
    AGENTIC       = "agentic"         # multi-step workflows, tool chains


@dataclass
class TaskSignals:
    """Structured signals extracted from a user message."""
    # Complexity score 0-20
    complexity: int = 0

    # Task type determined by dominant signal
    task_type: TaskType = TaskType.GENERAL

    # Individual signal scores (for debugging / logging)
    coding_score: int = 0
    reasoning_score: int = 0
    planning_score: int = 0
    multimodal_score: int = 0
    agentic_score: int = 0
    context_pressure: int = 0

    # Flags
    has_attachments: bool = False
    is_casual: bool = False
    estimated_tokens: int = 0


@dataclass
class RoutingDecision:
    """Final routing decision with resolved model string."""
    model_id: str                    # fully qualified provider:model_id string
    role: str                        # logical role used (orchestrator/coding/reasoning/multimodal)
    task_type: TaskType = TaskType.GENERAL
    signals: TaskSignals = field(default_factory=TaskSignals)
    confidence: float = 1.0
    reasoning: str = ""

    # Legacy fields kept for API compatibility with cli/main.py
    model_type: ModelType = ModelType.QWEN
    estimated_cost: float = 0.0
    estimated_tokens: int = 0
    complexity_score: int = 0


# ─────────────────────────────────────────────────────────
# Signal Extractor
# ─────────────────────────────────────────────────────────

# Keyword sets with weights
_CODING_KW = {
    # Core programming concepts – weight 2
    "def ": 2, "class ": 2, "import ": 2, "```python": 3, "```js": 3, "```ts": 3,
    "```rust": 3, "```go": 3, "```c++": 3, "```java": 3, "```sql": 2,
    # Action verbs – weight 1
    "code": 1, "program": 1, "function": 1, "implement": 1, "refactor": 1,
    "debug": 1, "fix": 1, "bug": 1, "error": 1, "exception": 1, "traceback": 1,
    "compile": 1, "algorithm": 1, "api": 1, "endpoint": 1, "database": 1,
    "script": 1, "test": 1, "unittest": 1, "pytest": 1, "deploy": 1,
    "docker": 1, "kubernetes": 1, "ci/cd": 1, "git": 1,
    # Specialist – weight 2
    "regex": 2, "recursion": 2, "async": 2, "concurrency": 2, "multithreading": 2,
    "optimize performance": 2, "big-o": 2, "complexity": 2,
}

_REASONING_KW = {
    # Deep analysis – weight 2
    "analyze": 2, "analyse": 2, "evaluate": 2, "critique": 2, "compare": 2,
    "pros and cons": 2, "trade-off": 2, "trade off": 2,
    # Logic / theory – weight 2
    "reason": 2, "logic": 2, "prove": 2, "hypothesis": 2, "causal": 2,
    "infer": 2, "deduce": 2, "theorem": 2,
    # Mathematics – weight 3
    "calculate": 3, "equation": 3, "integral": 3, "derivative": 3, "matrix": 3,
    "probability": 3, "statistics": 2, "regression": 2,
    # Research / strategy – weight 1
    "research": 1, "study": 1, "understand": 1, "explain": 1, "theory": 1,
}

_PLANNING_KW = {
    "plan": 2, "strategy": 2, "roadmap": 2, "design": 2, "architecture": 2,
    "system design": 3, "workflow": 2, "pipeline": 2, "multi-step": 3,
    "step by step": 2, "step-by-step": 2, "breakdown": 2, "outline": 1,
    "schedule": 1, "prioritize": 2, "requirements": 2, "specifications": 2,
}

_MULTIMODAL_KW = {
    "image": 3, "picture": 3, "photo": 3, "screenshot": 3, "diagram": 2,
    "chart": 2, "figure": 2, "graph": 2, "video": 3, "audio": 3,
    "listen": 2, "watch": 2, "visual": 2, "ocr": 3, "extract text": 3,
    "attached": 2, "attachment": 2, "[attached file": 3, "--- file reference": 3,
    "--- contents of": 2,
}

_AGENTIC_KW = {
    "autonomously": 3, "run continuously": 3, "keep running": 3,
    "do it yourself": 2, "execute": 2, "tool": 2, "browser": 2,
    "search the web": 2, "search online": 2, "open file": 2, "write file": 2,
    "terminal": 2, "shell command": 3, "run command": 2, "schedule": 2,
    "monitor": 2, "watch for": 2, "when x happens": 2,
}

_CASUAL_PATTERNS = [
    r"^hi\b", r"^hello\b", r"^hey\b", r"^sup\b", r"^yo\b",
    r"^thanks?\b", r"^ok\b", r"^okay\b", r"^sure\b", r"^cool\b",
    r"^lol\b", r"^haha\b", r"^nice\b", r"^great\b",
    r"^how are you", r"^what's up", r"^good morning", r"^good evening",
]


class TaskSignalExtractor:
    """
    Extracts structured signals from user input using weighted keyword sets
    and pattern rules.  No ML required – fast, deterministic, interpretable.
    """

    _casual_re = re.compile("|".join(_CASUAL_PATTERNS), re.IGNORECASE)

    @classmethod
    def extract(
        cls,
        user_input: str,
        context: Optional[List[Message]] = None,
    ) -> TaskSignals:
        sig = TaskSignals()
        text = user_input.lower()
        words = text.split()
        sig.estimated_tokens = max(1, len(words) * 3 // 2)

        # ── 1. Casual / trivial detection ─────────────────────────────
        if len(words) <= 8 and cls._casual_re.search(text.strip()):
            sig.is_casual = True
            sig.task_type = TaskType.CASUAL
            sig.complexity = 0
            return sig

        # ── 2. Attachment signals ──────────────────────────────────────
        for kw, w in _MULTIMODAL_KW.items():
            if kw in text:
                sig.multimodal_score += w
        if "[attached file:" in text or "--- file reference:" in text:
            sig.has_attachments = True
            sig.multimodal_score += 4

        # ── 3. Coding signals ──────────────────────────────────────────
        for kw, w in _CODING_KW.items():
            if kw in text:
                sig.coding_score += w
        # Code blocks are a very strong signal
        sig.coding_score += text.count("```") * 2

        # ── 4. Reasoning signals ───────────────────────────────────────
        for kw, w in _REASONING_KW.items():
            if kw in text:
                sig.reasoning_score += w

        # ── 5. Planning signals ────────────────────────────────────────
        for kw, w in _PLANNING_KW.items():
            if kw in text:
                sig.planning_score += w
        # Long structured messages with bullet points / numbered lists
        if re.search(r"^\s*[\-\*\d]\.", text, re.MULTILINE):
            sig.planning_score += 2

        # ── 6. Agentic signals ─────────────────────────────────────────
        for kw, w in _AGENTIC_KW.items():
            if kw in text:
                sig.agentic_score += w

        # ── 7. Context pressure ────────────────────────────────────────
        if context:
            if len(context) > 8:
                sig.context_pressure += 2
            if len(context) > 20:
                sig.context_pressure += 2
            total_chars = sum(len(m.content or "") for m in context)
            if total_chars > 4000:
                sig.context_pressure += 2
            if total_chars > 10000:
                sig.context_pressure += 2

        # ── 8. Message length pressure ────────────────────────────────
        if len(words) > 50:
            sig.coding_score += 1
            sig.reasoning_score += 1
        if len(words) > 150:
            sig.planning_score += 2

        # ── 9. Complexity & task type ──────────────────────────────────
        dominant = max(
            sig.coding_score,
            sig.reasoning_score + sig.planning_score,
            sig.multimodal_score,
            sig.agentic_score,
        )

        # Task type determined by highest-scoring dimension
        if sig.multimodal_score >= 3 and sig.multimodal_score >= dominant * 0.6:
            sig.task_type = TaskType.MULTIMODAL
        elif sig.agentic_score >= 4 and sig.agentic_score >= dominant * 0.6:
            sig.task_type = TaskType.AGENTIC
        elif sig.coding_score > sig.reasoning_score + sig.planning_score:
            sig.task_type = TaskType.CODING
        elif sig.reasoning_score + sig.planning_score >= 4:
            sig.task_type = TaskType.REASONING
        else:
            sig.task_type = TaskType.GENERAL

        # Raw complexity = sum of all signal scores + context pressure
        raw = (
            sig.coding_score
            + sig.reasoning_score
            + sig.planning_score
            + sig.multimodal_score // 2
            + sig.agentic_score // 2
            + sig.context_pressure
        )
        sig.complexity = min(20, raw)

        return sig


# ─────────────────────────────────────────────────────────
# Capability Matcher
# ─────────────────────────────────────────────────────────

# Provider-level capabilities (inherited by all models on that provider unless overridden)
_PROVIDER_CAPS: Dict[str, Dict[str, bool]] = {
    "google":    {"vision": True,  "audio": True,  "video": True, "tools": True, "long_context": True},
    "openai":    {"vision": True,  "audio": False, "video": False, "tools": True, "long_context": True},
    "anthropic": {"vision": True,  "audio": False, "video": False, "tools": True, "long_context": True},
    "groq":      {"vision": False, "audio": True,  "video": False, "tools": True, "long_context": False},
    "mistral":   {"vision": False, "audio": False, "video": False, "tools": True, "long_context": False},
    "openrouter":{"vision": False, "audio": False, "video": False, "tools": True, "long_context": True},
}

# Model ID substring overrides (checked after provider-level)
_MODEL_VISION_PATTERNS   = ["vision", "vl", "pixtral", "gpt-4o", "gemini", "claude-3", "qvq", "llava", "bakllava", "molmo"]
_MODEL_AUDIO_PATTERNS    = ["whisper", "audio", "voice", "tts", "speech", "stt"]
_MODEL_NO_TOOLS_PATTERNS = ["whisper", "tts", "speech", "stt", "embedding", "embed"]
_MODEL_STRONG_CODING     = ["deepseek", "codestral", "coder", "code-", "starcoder", "phind", "wizard-coder", "codellama"]
_MODEL_STRONG_REASONING  = ["o1", "o3", "r1", "reasoner", "claude-3-7", "claude-3-5", "thinking", "pro", "preview", "gemini-2.5-pro", "gemini-3.1-pro", "gemini-3.6", "opus"]
_MODEL_LONG_CONTEXT      = ["gemini", "claude", "gpt-4", "llama-3", "qwen", "mistral-large", "128k", "200k", "1m"]


class CapabilityMatcher:
    """
    Stateless, provider + model-ID keyword-rule capability inspector.
    No static model registry — works with any model string.
    """

    @staticmethod
    def _parse(model_id: str) -> Tuple[str, str]:
        """Return (provider, clean_model_id)."""
        m = model_id.strip()
        if ":" in m:
            prov, rest = m.split(":", 1)
            return prov.lower(), rest.lower()
        if "/" in m:
            prov = m.split("/")[0].lower()
            return prov, m.lower()
        return "openrouter", m.lower()

    @classmethod
    def get(cls, model_id: str) -> Dict[str, Any]:
        """Return a capability dict for any model_id string."""
        provider, mid = cls._parse(model_id)
        base = _PROVIDER_CAPS.get(provider, _PROVIDER_CAPS["openrouter"]).copy()

        # Vision override
        if any(p in mid for p in _MODEL_VISION_PATTERNS):
            base["vision"] = True
        # Audio override
        if any(p in mid for p in _MODEL_AUDIO_PATTERNS):
            base["audio"] = True
        # No tools for audio-only
        if any(p in mid for p in _MODEL_NO_TOOLS_PATTERNS):
            base["tools"] = False
        # Long context
        if any(p in mid for p in _MODEL_LONG_CONTEXT):
            base["long_context"] = True

        # Inferred strengths
        base["strong_coding"]    = any(p in mid for p in _MODEL_STRONG_CODING)
        base["strong_reasoning"] = any(p in mid for p in _MODEL_STRONG_REASONING)
        base["provider"]         = provider
        base["model_id"]         = mid

        return base

    @classmethod
    def supports_vision(cls, model_id: str) -> bool:
        return cls.get(model_id).get("vision", False)

    @classmethod
    def supports_tools(cls, model_id: str) -> bool:
        return cls.get(model_id).get("tools", True)

    @classmethod
    def is_audio_only(cls, model_id: str) -> bool:
        _, mid = cls._parse(model_id)
        return any(p in mid for p in _MODEL_AUDIO_PATTERNS)

    @classmethod
    def best_for_task(cls, model_ids: List[str], task_type: TaskType) -> Optional[str]:
        """
        Given a list of model_ids, return the best match for the task_type
        based on capability rules.  Returns None if the list is empty.
        """
        if not model_ids:
            return None
        scored: List[Tuple[int, str]] = []
        for mid in model_ids:
            caps = cls.get(mid)
            score = 0
            if task_type == TaskType.MULTIMODAL and caps.get("vision"):
                score += 3
            if task_type == TaskType.CODING and caps.get("strong_coding"):
                score += 3
            if task_type == TaskType.REASONING and caps.get("strong_reasoning"):
                score += 3
            if caps.get("tools"):
                score += 1
            if caps.get("long_context"):
                score += 1
            scored.append((score, mid))
        scored.sort(reverse=True)
        return scored[0][1]


# ─────────────────────────────────────────────────────────
# Role Resolver (Redis → SQLite → fallback)
# ─────────────────────────────────────────────────────────

# Sensible default model per role — only used if the user has not configured that role
_ROLE_FALLBACKS: Dict[str, str] = {
    "orchestrator": "openrouter:qwen/qwen3.7-flash",
    "coding":       "openrouter:deepseek/deepseek-v4-flash",
    "reasoning":    "openrouter:deepseek/deepseek-v4-pro",
    "multimodal":   "openrouter:google/gemini-2.5-flash-lite",
    "synthesizer":  "openrouter:google/gemini-2.5-flash-lite",
    "summary":      "openrouter:qwen/qwen3.7-flash",
}


def _resolve_role(role: str, memory_store=None) -> str:
    """
    Resolve the model string assigned to a role.
    Priority: Redis → SQLite → _ROLE_FALLBACKS → empty string.
    """
    try:
        from src.memory.redis_store import redis_store as rs
        if rs.is_connected():
            v = rs.get_role_model(role)
            if v and v.strip():
                return v.strip()
    except Exception:
        pass

    if memory_store is not None:
        try:
            db_roles = memory_store.get_role_assignments()
            item = db_roles.get(role)
            if item:
                if isinstance(item, dict):
                    prov = item.get("provider", "openrouter")
                    mid  = item.get("model_id", "")
                    if mid:
                        return f"{prov}:{mid}"
                elif isinstance(item, str) and item.strip():
                    return item.strip()
        except Exception:
            pass

    return _ROLE_FALLBACKS.get(role, "")


# ─────────────────────────────────────────────────────────
# Intelligent Router
# ─────────────────────────────────────────────────────────

# Complexity thresholds that upgrade the role
_CODING_UPGRADE_THRESHOLD    = 5   # coding task with score >= this → use coding role
_REASONING_UPGRADE_THRESHOLD = 6   # reasoning task with score >= this → use reasoning role
_AGENTIC_UPGRADE_THRESHOLD   = 4   # agentic task with score >= this → use reasoning (best planner)


class IntelligentRouter:
    """
    Routes a user message to the most appropriate assigned role model.

    Selection logic (in priority order):
        1. Multimodal signal  → multimodal role
        2. Agentic signal     → reasoning role  (best planner for tool chains)
        3. Coding signal      → coding role
        4. Reasoning/planning → reasoning role
        5. Otherwise          → orchestrator role (always-on default)

    For borderline tasks (signals don't meet thresholds), the orchestrator
    is used to keep latency + cost low.
    """

    def __init__(self, memory_store=None):
        self.memory_store = memory_store
        self.extractor = TaskSignalExtractor()
        self.capability_matcher = CapabilityMatcher()

    def _select_role(self, signals: TaskSignals) -> str:
        """Map extracted signals to the best logical role name."""
        if signals.is_casual:
            return "orchestrator"

        if signals.task_type == TaskType.MULTIMODAL:
            return "multimodal"

        if signals.task_type == TaskType.AGENTIC:
            if signals.agentic_score >= _AGENTIC_UPGRADE_THRESHOLD:
                return "reasoning"
            return "orchestrator"

        if signals.task_type == TaskType.CODING:
            if signals.coding_score >= _CODING_UPGRADE_THRESHOLD:
                return "coding"
            # Low-complexity coding → let orchestrator handle it
            return "orchestrator"

        if signals.task_type == TaskType.REASONING:
            if signals.reasoning_score + signals.planning_score >= _REASONING_UPGRADE_THRESHOLD:
                return "reasoning"
            return "orchestrator"

        return "orchestrator"

    def route(
        self,
        user_input: str,
        context: Optional[List[Message]] = None,
        force_role: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Synchronously produce a RoutingDecision.

        Args:
            user_input:  raw user message text
            context:     recent conversation messages (for context-pressure scoring)
            force_role:  if provided, skip analysis and route directly to this role
        """
        signals = TaskSignalExtractor.extract(user_input, context)

        # Role determination
        if force_role:
            selected_role = force_role
            reasoning = f"Role forced by caller: {force_role}"
        else:
            selected_role = self._select_role(signals)
            reasoning = (
                f"TaskType={signals.task_type.value} | "
                f"complexity={signals.complexity} | "
                f"coding={signals.coding_score} reasoning={signals.reasoning_score} "
                f"planning={signals.planning_score} multimodal={signals.multimodal_score} "
                f"agentic={signals.agentic_score} context={signals.context_pressure} "
                f"→ role={selected_role}"
            )

        # Resolve assigned model for that role
        model_id = _resolve_role(selected_role, self.memory_store)

        # Validate: if assigned multimodal model doesn't actually support vision,
        # fall back to orchestrator model (which user at least knows works)
        if selected_role == "multimodal" and model_id:
            if not CapabilityMatcher.supports_vision(model_id):
                fallback_orch = _resolve_role("orchestrator", self.memory_store)
                if CapabilityMatcher.supports_vision(fallback_orch):
                    model_id = fallback_orch
                    reasoning += " [multimodal model lacks vision → fell back to orchestrator]"

        # Legacy ModelType mapping for any remaining openrouter_client usage
        model_type = _model_id_to_legacy_type(model_id or "")

        return RoutingDecision(
            model_id=model_id,
            role=selected_role,
            task_type=signals.task_type,
            signals=signals,
            confidence=0.9,
            reasoning=reasoning,
            model_type=model_type,
            estimated_tokens=signals.estimated_tokens,
            complexity_score=signals.complexity,
        )


# ─────────────────────────────────────────────────────────
# Legacy shims  (keeps cli/main.py + openrouter_client working)
# ─────────────────────────────────────────────────────────

def _model_id_to_legacy_type(model_id: str) -> ModelType:
    mid = model_id.lower()
    if "qwen" in mid:
        return ModelType.QWEN
    if "gemini" in mid:
        return ModelType.GEMINI_FLASH
    if "mimo" in mid:
        return ModelType.MIMO
    if "deepseek" in mid:
        return ModelType.DEEPSEEK
    return ModelType.QWEN


class TaskAnalyzer:
    """Legacy compatibility shim — delegates to TaskSignalExtractor."""

    def calculate_complexity(self, user_input: str, context: Optional[List[Message]] = None) -> int:
        return TaskSignalExtractor.extract(user_input, context).complexity

    def determine_task_type(self, input_lower: str, score: int) -> TaskType:
        return TaskSignalExtractor.extract(input_lower).task_type


class ModelRouter:
    """
    Legacy compatibility shim — wraps IntelligentRouter with the old async API.
    cli/main.py uses this class.
    """

    def __init__(self, openrouter_client: OpenRouterClient):
        self.client = openrouter_client
        self.analyzer = TaskAnalyzer()
        # Try to share memory_store from client if available
        ms = getattr(openrouter_client, "memory_store", None)
        self._router = IntelligentRouter(memory_store=ms)

    async def route_task(
        self,
        user_input: str,
        context: Optional[List[Message]] = None,
        force_model: Optional[ModelType] = None,
    ) -> RoutingDecision:
        if force_model:
            # Build a minimal decision for explicit model override
            return RoutingDecision(
                model_id=str(force_model.value),
                role="orchestrator",
                task_type=TaskType.GENERAL,
                signals=TaskSignalExtractor.extract(user_input, context),
                reasoning=f"Model forced by caller: {force_model.value}",
                model_type=force_model,
            )

        decision = self._router.route(user_input, context)
        return decision

    def learn_from_feedback(self, *args, **kwargs):
        pass

    def get_routing_stats(self) -> Dict[str, Any]:
        return {"status": "IntelligentRouter active — role-based multi-signal routing"}

    async def self_improve(self):
        pass


# ─────────────────────────────────────────────────────────
# Convenience helper used by cli/main.py
# ─────────────────────────────────────────────────────────

async def route_and_execute(
    router: ModelRouter,
    user_input: str,
    system_prompt: str = "You are a helpful AI assistant.",
    context: Optional[List[Message]] = None,
    stream: bool = False,
) -> Tuple[RoutingDecision, str]:
    """Route task and execute in one call (cli helper)."""
    from src.models.openrouter_client import create_messages

    decision = await router.route_task(user_input, context)
    print(f"[Router] role={decision.role} | task={decision.task_type.value} | "
          f"complexity={decision.complexity_score} | model={decision.model_id}")
    print(f"[Router] {decision.reasoning}")

    messages = context if context else create_messages(system_prompt, user_input)
    client = OpenRouterClient()

    try:
        if stream:
            parts = []
            async for chunk in client.chat_completion_stream(messages=messages, model_type=decision.model_type):
                parts.append(chunk)
                print(chunk, end="", flush=True)
            print()
            return decision, "".join(parts)
        else:
            resp = await client.chat_completion(messages=messages, model_type=decision.model_type)
            return decision, resp.choices[0]["message"]["content"]
    finally:
        await client.close()