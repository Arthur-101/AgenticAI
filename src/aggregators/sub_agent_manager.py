"""
Sub-Agent Manager with Hub-and-Spoke Relay Architecture.

Each sub-agent knows about its peers through an "Agent Card" — a compact capability
description. When a sub-agent needs help from a peer (e.g., the Coding Agent wants
the Reasoning Agent to review its code), it emits a REQUEST_PEER signal which the
SubAgentManager (main controller / relay hub) routes to the correct peer and feeds
the response back as context before the requesting agent finalizes its answer.

Flow:
    User Prompt
        ↓
    Stage 1: Reasoning Agent analyses the problem → produces Architecture Plan
        ↓ (plan relayed as context to Coding Agent)
    Stage 2: Coding Agent receives plan + user prompt → implements it
        ↓ (code relayed back to Reasoning Agent for optional peer-review)
    Stage 3: Optional – Reasoning Agent reviews code, emits LGTM or corrections
        ↓
    ConsensusAggregator produces unified master response
"""
import asyncio
import json
import sys
import logging
from typing import Dict, Any, List, Optional

from src.memory.redis_store import redis_store
from src.models.provider_router import ProviderRouter

logger = logging.getLogger(__name__)

# ── Agent capability cards (what each sub-agent is and what it can do) ──────────
AGENT_CARDS = {
    "reasoning": {
        "name": "💡 Reasoning & Architecture Agent",
        "model": "deepseek/deepseek-v4-pro",
        "description": (
            "Expert in step-by-step logical decomposition, system architecture, "
            "design patterns, security analysis, and edge-case identification. "
            "Produces structured architectural plans and reviewes code for correctness."
        ),
    },
    "coding": {
        "name": "🤖 Coding & Execution Agent",
        "model": "deepseek/deepseek-v4-flash",
        "description": (
            "Expert in writing production-ready, well-typed, fully-functional Python "
            "(and other languages) code with proper error handling, type annotations, "
            "docstrings, and unit-test stubs."
        ),
    },
    "multimodal": {
        "name": "👁️ Multimodal & Vision Specialist",
        "model": "google/gemini-2.5-flash-lite",
        "description": (
            "Expert in analysing attached images, screenshots, UI wireframes, "
            "PDF documents, audio/video metadata, and other non-text content. "
            "Extracts key visual and structural details for the team."
        ),
    },
}


def _build_team_intro(active_roles: List[str]) -> str:
    """Build a compact team introduction paragraph injected into every agent's system prompt."""
    lines = ["You are part of a Multi-Model AI Agent Team. The team members and their roles are:\n"]
    for role in active_roles:
        card = AGENT_CARDS[role]
        lines.append(f"  • {card['name']} ({card['model']}): {card['description']}")
    lines.append(
        "\nThe Main Controller (relay hub) coordinates the team. "
        "If your response needs input from another team member, you may flag it "
        "as 'RELAY_REQUEST:<peer_role>:<your_question>' on its own line, and the "
        "controller will route that question to the correct peer and return the answer to you."
    )
    return "\n".join(lines)


class SubAgentManager:
    """
    Hub-and-spoke relay manager for multi-agent collaboration.

    Stages:
      1. Reasoning Agent → produces architectural analysis / plan.
      2. Coding Agent → receives the plan as relay context → implements it.
      3. (Optional) Reasoning Agent → reviews code → flags issues or confirms LGTM.
      4. Multimodal Agent (if attachments present) runs independently & in parallel with stage 1.
    """

    RELAY_PREFIX = "RELAY_REQUEST:"

    def __init__(self, openrouter_client):
        self.client = openrouter_client
        self.provider_router = ProviderRouter(openrouter_client)

    def _get_dynamic_model_for_role(self, role: str, default_model: str) -> str:
        """Fetch role model override from Redis or SQLite if available."""
        # 1. Try Redis
        if redis_store.is_connected():
            redis_model = redis_store.get_role_model(role)
            if redis_model and redis_model.strip():
                val = redis_model.strip()
                if ":" in val:
                    prov, mid = val.split(":", 1)
                    if prov in ["google", "openai", "anthropic"] and not mid.startswith(f"{prov}/"):
                        return f"{prov}/{mid}"
                    return mid
                return val
        # 2. Try SQLite
        try:
            db_roles = self.provider_router.memory_store.get_role_assignments()
            if role.lower() in db_roles:
                item = db_roles[role.lower()]
                if isinstance(item, dict):
                    prov = item.get("provider", "openrouter")
                    mid = item.get("model_id", "")
                    if mid:
                        if prov in ["google", "openai", "anthropic"] and not mid.startswith(f"{prov}/"):
                            return f"{prov}/{mid}"
                        return mid
                elif isinstance(item, str) and item.strip():
                    return item.strip()
        except Exception:
            pass
        return default_model

    # ── Public API ───────────────────────────────────────────────────────────────

    async def run_collaborative_team(
        self,
        user_message: str,
        context: List[Dict[str, Any]],
        has_multimodal_attachments: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Execute a hub-and-spoke collaborative team run and return each agent's output.

        Returns a list of result dicts:
            {"role": str, "model_id": str, "content": str, "tokens_used": int}
        """
        active_roles = ["reasoning", "coding"]
        if has_multimodal_attachments:
            active_roles.append("multimodal")

        team_intro = _build_team_intro(active_roles)
        print(
            f"🚀 Launching Multi-Model Team ({len(active_roles)} agents): "
            + ", ".join(active_roles),
            file=sys.stderr, flush=True,
        )

        results: List[Dict[str, Any]] = []

        # ── Stage 1: Reasoning Agent + Multimodal (in parallel) ──────────────
        stage1_tasks = [self._run_reasoning_agent(user_message, context, team_intro)]
        if has_multimodal_attachments:
            stage1_tasks.append(self._run_multimodal_agent(user_message, context, team_intro))

        stage1_outputs = await asyncio.gather(*stage1_tasks)
        reasoning_result = stage1_outputs[0]
        results.append(reasoning_result)
        if has_multimodal_attachments and len(stage1_outputs) > 1:
            results.append(stage1_outputs[1])

        # ── Stage 2: Coding Agent (receives reasoning plan as relay context) ──
        coding_result = await self._run_coding_agent(
            user_message=user_message,
            context=context,
            team_intro=team_intro,
            reasoning_plan=reasoning_result["content"],
        )
        results.append(coding_result)

        # ── Stage 3: Reasoning Agent reviews the code (optional peer review) ──
        review_result = await self._run_code_review(
            user_message=user_message,
            team_intro=team_intro,
            reasoning_plan=reasoning_result["content"],
            code_output=coding_result["content"],
        )
        if review_result:
            results.append(review_result)

        return results

    # ── Private stage runners ─────────────────────────────────────────────────

    async def _run_reasoning_agent(
        self,
        user_message: str,
        context: List[Dict[str, Any]],
        team_intro: str,
    ) -> Dict[str, Any]:
        card = AGENT_CARDS["reasoning"]
        system = (
            f"{team_intro}\n\n"
            f"YOUR ROLE: {card['name']}\n"
            "TASK:\n"
            "1. Analyse the user's request thoroughly.\n"
            "2. Produce a clear, structured ARCHITECTURAL PLAN with:\n"
            "   - Problem breakdown\n"
            "   - Recommended approach & design patterns\n"
            "   - Security / edge-case considerations\n"
            "   - Exact steps the Coding Agent should follow\n"
            "3. Do NOT write the implementation code yourself — the Coding Agent will do that.\n"
            "4. Keep your plan focused and actionable."
        )
        model_id = self._get_dynamic_model_for_role("reasoning", card["model"])
        return await self._call_agent("reasoning", model_id, system, user_message, context)

    async def _run_multimodal_agent(
        self,
        user_message: str,
        context: List[Dict[str, Any]],
        team_intro: str,
    ) -> Dict[str, Any]:
        card = AGENT_CARDS["multimodal"]
        system = (
            f"{team_intro}\n\n"
            f"YOUR ROLE: {card['name']}\n"
            "TASK: Analyse any attached files/images/media referenced in the user message. "
            "Extract key visual, structural, and contextual details that will help the "
            "Reasoning and Coding agents understand what the user has shared."
        )
        model_id = self._get_dynamic_model_for_role("multimodal", card["model"])
        return await self._call_agent("multimodal", model_id, system, user_message, context)

    async def _run_coding_agent(
        self,
        user_message: str,
        context: List[Dict[str, Any]],
        team_intro: str,
        reasoning_plan: str,
    ) -> Dict[str, Any]:
        card = AGENT_CARDS["coding"]
        relay_context = (
            "── RELAY FROM 💡 Reasoning & Architecture Agent ──\n"
            f"{reasoning_plan}\n"
            "── END RELAY ──\n\n"
            "Implement the architectural plan above for the user's request. "
            "Follow the plan exactly. Write complete, production-ready code."
        )
        system = (
            f"{team_intro}\n\n"
            f"YOUR ROLE: {card['name']}\n"
            "TASK:\n"
            "1. You have received the architectural plan from the Reasoning Agent (see RELAY below).\n"
            "2. Implement it faithfully — write complete, production-ready, well-typed code.\n"
            "3. Include type annotations, docstrings, and error handling.\n"
            "4. Do NOT re-explain the architecture — the Reasoning Agent already did that."
        )
        combined_message = f"{relay_context}\n\nOriginal user request:\n{user_message}"
        model_id = self._get_dynamic_model_for_role("coding", card["model"])
        return await self._call_agent("coding", model_id, system, combined_message, context)

    async def _run_code_review(
        self,
        user_message: str,
        team_intro: str,
        reasoning_plan: str,
        code_output: str,
    ) -> Optional[Dict[str, Any]]:
        """Reasoning Agent peer-reviews the Coding Agent's output."""
        if len(code_output) < 200 or "[Worker failed" in code_output:
            return None

        card = AGENT_CARDS["reasoning"]
        system = (
            f"{team_intro}\n\n"
            f"YOUR ROLE: {card['name']} — Code Reviewer\n"
            "TASK:\n"
            "The Coding Agent has produced an implementation based on your architectural plan.\n"
            "Review it for:\n"
            "  - Correctness against your plan\n"
            "  - Potential bugs or missing edge-case handling\n"
            "  - Security concerns\n"
            "  - Anything the Consensus Synthesizer should be aware of\n"
            "Be concise. Output either '✅ LGTM' with brief notes, or specific corrections."
        )
        review_message = (
            f"Original user request:\n{user_message}\n\n"
            f"My architectural plan:\n{reasoning_plan}\n\n"
            f"Coding Agent's implementation:\n{code_output}"
        )
        model_id = self._get_dynamic_model_for_role("reasoning", card["model"])
        result = await self._call_agent("reasoning_review", model_id, system, review_message, [])
        return result

    # ── Core call helper ──────────────────────────────────────────────────────

    async def _call_agent(
        self,
        role: str,
        model_id: str,
        system_prompt: str,
        user_message: str,
        context: List[Dict[str, Any]],
        max_tokens: int = 2500,
    ) -> Dict[str, Any]:
        messages = [{"role": "system", "content": system_prompt}]
        for msg in context[-3:]:
            if msg.get("content"):
                messages.append({"role": msg.get("role", "user"), "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        fallback_model = "qwen/qwen3.5-flash-02-23"
        try:
            response = await self.provider_router.generate(
                messages=messages,
                model_id=model_id,
                temperature=0.2,
                max_tokens=max_tokens,
            )
            content = response.get("content", "").strip()
        except Exception as e:
            logger.error(f"Sub-agent [{role}|{model_id}] failed: {e}. Falling back to {fallback_model}.")
            try:
                response = await self.provider_router.generate(
                    messages=messages,
                    model_id=fallback_model,
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
                content = response.get("content", "").strip()
                model_id = fallback_model
            except Exception as fe:
                content = f"[Agent {role} failed: {fe}]"
                response = {"tokens_used": 0}

        # Stream live sub-agent output to UI via stderr
        log_payload = json.dumps({"role": role, "model": model_id, "reply": content[:300]})
        print(f"SUB_AGENT_MSG:{log_payload}", file=sys.stderr, flush=True)
        print(f"✅ Sub-agent [{role}] completed.", file=sys.stderr, flush=True)

        return {
            "role": role,
            "model_id": model_id,
            "content": content,
            "tokens_used": response.get("tokens_used", 0),
        }
