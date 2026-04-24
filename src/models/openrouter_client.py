import asyncio
import json
import time
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import httpx
from pydantic import BaseModel, Field
import tiktoken

from src.utils.config import config


class ModelType(Enum):
    """Available model types."""
    QWEN = "qwen"
    GEMINI_FLASH = "gemini_flash"
    MIMO = "mimo"
    DEEPSEEK = "deepseek"
    GEMINI_PRO = "gemini_pro"


class Message(BaseModel):
    """Chat message."""
    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request."""
    model: str = Field(..., description="Model ID")
    messages: List[Message] = Field(..., description="Chat messages")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Whether to stream response")


class UsageDetails(BaseModel):
    """Usage details from OpenRouter."""
    prompt_tokens: int = Field(..., description="Prompt tokens")
    completion_tokens: int = Field(..., description="Completion tokens")
    total_tokens: int = Field(..., description="Total tokens")
    cost: float = Field(..., description="Cost in USD")
    is_byok: bool = Field(default=False, description="Is BYOK (Bring Your Own Key)")
    prompt_tokens_details: Optional[Dict[str, int]] = Field(default=None, description="Prompt token details")
    cost_details: Optional[Dict[str, float]] = Field(default=None, description="Cost details")
    completion_tokens_details: Optional[Dict[str, int]] = Field(default=None, description="Completion token details")


class ChatResponse(BaseModel):
    """Chat completion response."""
    id: str = Field(..., description="Response ID")
    object: str = Field(..., description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Model provider")
    system_fingerprint: Optional[str] = Field(default=None, description="System fingerprint")
    choices: List[Dict[str, Any]] = Field(..., description="Response choices")
    usage: Optional[UsageDetails] = Field(default=None, description="Token usage")


@dataclass
class ModelCapabilities:
    """Model capabilities for routing decisions."""
    max_tokens: int
    supports_tools: bool
    supports_vision: bool
    reasoning_strength: float  # 0-1 scale
    coding_strength: float  # 0-1 scale
    speed: float  # 0-1 scale (higher = faster)
    cost_per_token: float  # USD per 1M tokens (average)


class OpenRouterClient:
    """Client for OpenRouter API."""
    
    def __init__(self):
        self.base_url = config.settings.openrouter_base_url
        self.api_key = config.settings.openrouter_api_key
        self.client = httpx.AsyncClient(
            timeout=config.settings.request_timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://agenticai.local",  # Optional
                "X-Title": "AgenticAI",  # Optional
            }
        )
        
        # Model ID mapping
        self.model_ids = {
            ModelType.QWEN: config.settings.model_qwen,
            ModelType.GEMINI_FLASH: config.settings.model_gemini_flash,
            ModelType.MIMO: config.settings.model_mimo,
            ModelType.DEEPSEEK: config.settings.model_deepseek,
            ModelType.GEMINI_PRO: config.settings.model_gemini_pro,
        }
        
        # Model capabilities (approximate, based on documentation)
        self.model_capabilities = {
            ModelType.QWEN: ModelCapabilities(
                max_tokens=32768,
                supports_tools=True,
                supports_vision=False,
                reasoning_strength=0.7,
                coding_strength=0.6,
                speed=0.8,
                cost_per_token=0.5,
            ),
            ModelType.GEMINI_FLASH: ModelCapabilities(
                max_tokens=8192,
                supports_tools=True,
                supports_vision=True,
                reasoning_strength=0.5,
                coding_strength=0.4,
                speed=0.9,
                cost_per_token=0.2,
            ),
            ModelType.MIMO: ModelCapabilities(
                max_tokens=32768,
                supports_tools=True,
                supports_vision=True,
                reasoning_strength=0.9,
                coding_strength=0.7,
                speed=0.6,
                cost_per_token=3.0,
            ),
            ModelType.DEEPSEEK: ModelCapabilities(
                max_tokens=128000,
                supports_tools=True,
                supports_vision=False,
                reasoning_strength=0.6,
                coding_strength=0.9,
                speed=0.7,
                cost_per_token=0.21,
            ),
            ModelType.GEMINI_PRO: ModelCapabilities(
                max_tokens=32768,
                supports_tools=True,
                supports_vision=True,
                reasoning_strength=0.8,
                coding_strength=0.7,
                speed=0.5,
                cost_per_token=3.125,
            ),
        }
        
        # Tokenizer for approximate token counting
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except:
            self.tokenizer = None
    
    async def chat_completion(
        self,
        messages: List[Message],
        model_type: ModelType,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> ChatResponse:
        """Send chat completion request to OpenRouter."""
        model_id = self.model_ids[model_type]
        
        # Use defaults if not provided
        if temperature is None:
            temperature = config.settings.temperature
        if max_tokens is None:
            max_tokens = min(
                config.settings.max_tokens_per_request,
                self.model_capabilities[model_type].max_tokens
            )
        
        request = ChatRequest(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=request.dict(exclude_none=True),
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Track cost
            if "usage" in data:
                usage = data["usage"]
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                config.track_cost(model_id, input_tokens, output_tokens)
            
            return ChatResponse(**data)
            
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error in chat completion: {e}")
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Message],
        model_type: ModelType,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion response."""
        model_id = self.model_ids[model_type]
        
        if temperature is None:
            temperature = config.settings.temperature
        if max_tokens is None:
            max_tokens = min(
                config.settings.max_tokens_per_request,
                self.model_capabilities[model_type].max_tokens
            )
        
        request = ChatRequest(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=request.dict(exclude_none=True),
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                
                collected_content = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        
                        try:
                            chunk = json.loads(data)
                            if "choices" in chunk and chunk["choices"]:
                                delta = chunk["choices"][0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    content = delta["content"]
                                    collected_content.append(content)
                                    yield content
                        except json.JSONDecodeError:
                            continue
            
            # Track cost (approximate)
            if self.tokenizer and collected_content:
                full_response = "".join(collected_content)
                output_tokens = len(self.tokenizer.encode(full_response))
                # Estimate input tokens
                input_messages = "\n".join([m.content for m in messages])
                input_tokens = len(self.tokenizer.encode(input_messages))
                config.track_cost(model_id, input_tokens, output_tokens)
                
        except Exception as e:
            print(f"Error in streaming: {e}")
            raise
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Fallback: approximate 4 chars per token
        return len(text) // 4
    
    def get_model_capabilities(self, model_type: ModelType) -> ModelCapabilities:
        """Get capabilities for a model."""
        return self.model_capabilities[model_type]
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models with capabilities."""
        models = []
        for model_type, model_id in self.model_ids.items():
            caps = self.model_capabilities[model_type]
            models.append({
                "type": model_type.value,
                "id": model_id,
                "capabilities": {
                    "max_tokens": caps.max_tokens,
                    "supports_tools": caps.supports_tools,
                    "supports_vision": caps.supports_vision,
                    "reasoning_strength": caps.reasoning_strength,
                    "coding_strength": caps.coding_strength,
                    "speed": caps.speed,
                    "cost_per_token": caps.cost_per_token,
                }
            })
        return models
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Helper function to create message list
def create_messages(system_prompt: str, user_message: str) -> List[Message]:
    """Create message list from system prompt and user message."""
    return [
        Message(role="system", content=system_prompt),
        Message(role="user", content=user_message),
    ]