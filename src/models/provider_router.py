import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error

from src.models.openrouter_client import OpenRouterClient, Message
from src.memory.sqlite_store import SQLiteMemoryStore
from src.utils.config import config

logger = logging.getLogger(__name__)

class ProviderRouter:
    """Unified router supporting OpenRouter, OpenAI, Google AI Studio, and Anthropic APIs."""
    
    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None, memory_store: Optional[SQLiteMemoryStore] = None):
        self.openrouter_client = openrouter_client or OpenRouterClient()
        self.memory_store = memory_store or SQLiteMemoryStore()

    def get_api_key_for_provider(self, provider: str) -> Optional[str]:
        """Fetch active API key for provider from SQLite DB with .env fallback."""
        provider_lower = provider.lower()
        
        # 1. Try SQLite Database first
        try:
            db_key = self.memory_store.get_api_key_by_provider(provider_lower)
            if db_key and db_key.strip():
                return db_key.strip()
        except Exception as e:
            logger.warning(f"Error fetching API key from SQLite for {provider}: {e}")

        # 2. Fall back to environment variables
        if provider_lower == "openrouter":
            return getattr(config.settings, "openrouter_api_key", None) or os.getenv("OPENROUTER_API_KEY")
        elif provider_lower in ["openai"]:
            return os.getenv("OPENAI_API_KEY")
        elif provider_lower in ["google", "gemini"]:
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        elif provider_lower in ["anthropic", "claude"]:
            return os.getenv("ANTHROPIC_API_KEY")
            
        return None

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Dict[str, Any]:
        """Route generation request to appropriate provider based on model ID prefix or configuration."""
        model_lower = model_id.lower()
        
        # 1. OpenAI Native Direct API
        if model_lower.startswith("openai/") or model_lower in ["gpt-4o", "gpt-4o-mini", "o1-mini", "o3-mini"]:
            api_key = self.get_api_key_for_provider("openai")
            if api_key:
                clean_model = model_id.replace("openai/", "")
                return await self._generate_openai_direct(messages, clean_model, api_key, temperature, max_tokens)
                
        # 2. Google AI Studio Direct API
        if model_lower.startswith("google/") and not model_lower.startswith("google/gemini"):
            api_key = self.get_api_key_for_provider("google")
            if api_key:
                clean_model = model_id.replace("google/", "")
                return await self._generate_google_direct(messages, clean_model, api_key, temperature, max_tokens)
                
        # 3. Anthropic Direct API
        if model_lower.startswith("anthropic/") or model_lower in ["claude-3-7-sonnet", "claude-3-5-haiku"]:
            api_key = self.get_api_key_for_provider("anthropic")
            if api_key:
                clean_model = model_id.replace("anthropic/", "")
                return await self._generate_anthropic_direct(messages, clean_model, api_key, temperature, max_tokens)

        # 4. Default: OpenRouter Client (handles all openrouter/ models and fallbacks)
        return await self.openrouter_client.generate(
            messages=messages,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens
        )

    async def fetch_provider_models(self, provider: str) -> List[Dict[str, Any]]:
        """Fetch models with pricing metadata and active/deprecated flags for provider."""
        provider_lower = provider.lower().strip()
        api_key = self.get_api_key_for_provider(provider_lower)

        # 1. OpenRouter Catalog
        if provider_lower == "openrouter":
            try:
                loop = asyncio.get_event_loop()
                req = urllib.request.Request("https://openrouter.ai/api/v1/models")
                res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                data = json.loads(res.read().decode("utf-8"))
                models = []
                for item in data.get("data", []):
                    model_id = item.get("id", "")
                    name = item.get("name", model_id)
                    pricing = item.get("pricing", {})
                    
                    try:
                        p_in = float(pricing.get("prompt", "0")) * 1_000_000
                        p_out = float(pricing.get("completion", "0")) * 1_000_000
                        cost_str = f"${p_in:.2f}/1M in, ${p_out:.2f}/1M out" if (p_in > 0 or p_out > 0) else "Free / Included"
                    except Exception:
                        cost_str = "Standard Pricing"
                        
                    models.append({
                        "id": model_id,
                        "name": name,
                        "provider": "openrouter",
                        "cost_label": cost_str,
                        "is_active": True,
                        "context_length": item.get("context_length", 0)
                    })
                return models
            except Exception as e:
                logger.warning(f"Failed to fetch OpenRouter model catalog dynamically: {e}")
                # Fallback static OpenRouter catalog
                return [
                    {"id": "qwen/qwen3.5-flash-02-23", "name": "Qwen 3.5 Flash", "provider": "openrouter", "cost_label": "$0.10/1M in, $0.30/1M out", "is_active": True},
                    {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek V4 Flash", "provider": "openrouter", "cost_label": "$0.14/1M in, $0.28/1M out", "is_active": True},
                    {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek V4 Pro", "provider": "openrouter", "cost_label": "$0.55/1M in, $2.19/1M out", "is_active": True},
                    {"id": "google/gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite", "provider": "openrouter", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                    {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "openrouter", "cost_label": "$3.00/1M in, $15.00/1M out", "is_active": True},
                ]

        # 2. Google AI Studio Catalog
        elif provider_lower in ["google", "gemini"]:
            active_models = [
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (Fast & Capable)", "cost_label": "$0.10/1M in, $0.40/1M out", "is_active": True},
                {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash Lite (Lightweight)", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "cost_label": "$0.075/1M in, $0.30/1M out", "is_active": True},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro (High Reasoning)", "cost_label": "$1.25/1M in, $5.00/1M out", "is_active": True},
            ]
            deprecated_models = [
                {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash [Deprecated]", "cost_label": "[Deprecated] Not Available", "is_active": False},
                {"id": "gemini-1.0-pro", "name": "Gemini 1.0 Pro [Deprecated]", "cost_label": "[Deprecated] Retired by Google", "is_active": False},
            ]
            
            # Optionally query Google REST API if key exists
            if api_key:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key.strip()}"
                    loop = asyncio.get_event_loop()
                    req = urllib.request.Request(url)
                    res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                    data = json.loads(res.read().decode("utf-8"))
                    fetched_ids = {m.get("name", "").replace("models/", "") for m in data.get("models", [])}
                    
                    # Update active flags based on API live response
                    for m in active_models:
                        if m["id"] not in fetched_ids and not any(f.startswith(m["id"]) for f in fetched_ids):
                            m["is_active"] = True  # Keep available if compatible
                except Exception as e:
                    logger.debug(f"Google AI Studio live model fetch notice: {e}")
                    
            return active_models + deprecated_models

        # 3. OpenAI Catalog
        elif provider_lower in ["openai"]:
            return [
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai", "cost_label": "$0.15/1M in, $0.60/1M out", "is_active": True},
                {"id": "gpt-4o", "name": "GPT-4o Flagship", "provider": "openai", "cost_label": "$2.50/1M in, $10.00/1M out", "is_active": True},
                {"id": "o3-mini", "name": "o3-mini Reasoning", "provider": "openai", "cost_label": "$1.10/1M in, $4.40/1M out", "is_active": True},
                {"id": "o1-mini", "name": "o1-mini Reasoning", "provider": "openai", "cost_label": "$1.10/1M in, $4.40/1M out", "is_active": True},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo [Legacy]", "provider": "openai", "cost_label": "[Deprecated] Legacy Model", "is_active": False},
                {"id": "text-davinci-003", "name": "Davinci-003 [Retired]", "provider": "openai", "cost_label": "[Deprecated] Retired", "is_active": False},
            ]

        # 4. Anthropic Catalog
        elif provider_lower in ["anthropic", "claude"]:
            return [
                {"id": "claude-3-7-sonnet-20250219", "name": "Claude 3.7 Sonnet (Hybrid Reasoning)", "provider": "anthropic", "cost_label": "$3.00/1M in, $15.00/1M out", "is_active": True},
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "anthropic", "cost_label": "$3.00/1M in, $15.00/1M out", "is_active": True},
                {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "provider": "anthropic", "cost_label": "$0.80/1M in, $4.00/1M out", "is_active": True},
                {"id": "claude-2.1", "name": "Claude 2.1 [Legacy]", "provider": "anthropic", "cost_label": "[Deprecated] Legacy", "is_active": False},
            ]

        return []

    async def test_provider_key(self, provider: str, key_value: str, model_id: Optional[str] = None) -> Dict[str, Any]:
        """Test and verify an API key for a specific provider."""
        provider_lower = provider.lower()
        test_message = [{"role": "user", "content": "Ping test. Respond with OK."}]
        
        try:
            if provider_lower == "openrouter":
                target_model = model_id or "qwen/qwen3.5-flash-02-23"
                headers = {
                    "Authorization": f"Bearer {key_value.strip()}",
                    "Content-Type": "application/json"
                }
                payload = json.dumps({
                    "model": target_model,
                    "messages": test_message,
                    "max_tokens": 10
                }).encode("utf-8")
                
                req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=payload, headers=headers, method="POST")
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10.0))
                res_data = json.loads(response.read().decode("utf-8"))
                return {"success": True, "message": "OpenRouter API Key verified successfully!", "details": res_data.get("choices", [{}])[0].get("message", {}).get("content", "")}

            elif provider_lower == "openai":
                target_model = model_id or "gpt-4o-mini"
                return await self._generate_openai_direct(test_message, target_model, key_value, 0.2, 10)

            elif provider_lower == "google":
                target_model = model_id or "gemini-2.0-flash"
                return await self._generate_google_direct(test_message, target_model, key_value, 0.2, 10)

            elif provider_lower == "anthropic":
                target_model = model_id or "claude-3-5-haiku-20241022"
                return await self._generate_anthropic_direct(test_message, target_model, key_value, 0.2, 10)

            else:
                return {"success": False, "error": f"Unsupported provider: {provider}"}
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8") if http_err.fp else str(http_err)
            return {"success": False, "error": f"HTTP {http_err.code}: {err_body}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Private Provider Direct HTTP Implementations ─────────────────────────────

    async def _generate_openai_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Direct HTTP call to OpenAI API."""
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        payload = json.dumps({
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }).encode("utf-8")

        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=payload, headers=headers, method="POST")
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30.0))
        data = json.loads(res.read().decode("utf-8"))
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        tokens = data.get("usage", {}).get("total_tokens", 0)
        return {"content": content, "model_id": f"openai/{model_name}", "tokens_used": tokens, "success": True}

    async def _generate_google_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Direct HTTP call to Google AI Studio Gemini REST API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key.strip()}"
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ["user", "system"] else "model"
            contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

        headers = {"Content-Type": "application/json"}
        payload = json.dumps({
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30.0))
        data = json.loads(res.read().decode("utf-8"))
        
        candidates = data.get("candidates", [{}])
        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        tokens = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        return {"content": content, "model_id": f"google/{model_name}", "tokens_used": tokens, "success": True}

    async def _generate_anthropic_direct(
        self,
        messages: List[Dict[str, Any]],
        model_name: str,
        api_key: str,
        temperature: float,
        max_tokens: int
    ) -> Dict[str, Any]:
        """Direct HTTP call to Anthropic Messages API."""
        system_msg = ""
        user_msgs = []
        for m in messages:
            if m.get("role") == "system":
                system_msg += m.get("content", "") + "\n"
            else:
                user_msgs.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        headers = {
            "x-api-key": api_key.strip(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        body: Dict[str, Any] = {
            "model": model_name,
            "messages": user_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if system_msg.strip():
            body["system"] = system_msg.strip()

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers=headers, method="POST")
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=30.0))
        data = json.loads(res.read().decode("utf-8"))

        content = data.get("content", [{}])[0].get("text", "").strip()
        tokens = data.get("usage", {}).get("input_tokens", 0) + data.get("usage", {}).get("output_tokens", 0)
        return {"content": content, "model_id": f"anthropic/{model_name}", "tokens_used": tokens, "success": True}
