import re
import json
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from dataclasses import dataclass
import time

from src.models.openrouter_client import ModelType, Message, OpenRouterClient
from src.utils.config import config


class TaskType(Enum):
    """Task types for model routing."""
    SIMPLE_CHAT = "simple_chat"
    CODING = "coding"
    COMPLEX_REASONING = "complex_reasoning"
    MULTIMODAL = "multimodal"
    UNKNOWN = "unknown"


@dataclass
class RoutingDecision:
    """Routing decision for a task."""
    model_type: ModelType
    task_type: TaskType
    confidence: float
    reasoning: str
    estimated_cost: float = 0.0
    estimated_tokens: int = 0


class TaskAnalyzer:
    """Analyzes tasks to determine their type and requirements."""
    
    # Patterns for task classification
    CODING_PATTERNS = [
        r"code\b", r"program\b", r"function\b", r"class\b", r"def\s+\w+",
        r"import\s+\w+", r"from\s+\w+", r"python\b", r"javascript\b", r"typescript\b",
        r"java\b", r"cpp\b", r"c\+\+\b", r"c#\b", r"go\b", r"rust\b", r"html\b",
        r"css\b", r"sql\b", r"algorithm\b", r"data structure\b", r"bug\b", r"fix\b",
        r"error\b", r"exception\b", r"debug\b", r"implement\b", r"write.*code",
        r"create.*function", r"build.*app", r"develop.*software",
    ]
    
    COMPLEX_REASONING_PATTERNS = [
        r"analyze\b", r"reason\b", r"explain\b", r"understand\b", r"concept\b",
        r"theory\b", r"philosophy\b", r"logic\b", r"mathematics\b", r"physics\b",
        r"chemistry\b", r"biology\b", r"science\b", r"research\b", r"study\b",
        r"compare.*contrast", r"advantages.*disadvantages", r"pros.*cons",
        r"critical.*thinking", r"problem.*solving", r"decision.*making",
        r"plan\b", r"strategy\b", r"design\b", r"architecture\b",
    ]
    
    MULTIMODAL_PATTERNS = [
        r"image\b", r"picture\b", r"photo\b", r"visual\b", r"see\b", r"look\b",
        r"describe.*image", r"what.*picture", r"show\b", r"display\b",
        r"chart\b", r"graph\b", r"diagram\b", r"figure\b", r"drawing\b",
        r"screenshot\b", r"photo.*show", r"image.*describe",
    ]
    
    SIMPLE_CHAT_PATTERNS = [
        r"hi\b", r"hello\b", r"hey\b", r"how.*you", r"what.*up", r"good morning",
        r"good afternoon", r"good evening", r"thanks\b", r"thank you", r"please\b",
        r"help\b", r"can you", r"could you", r"would you", r"tell me",
        r"what is", r"who is", r"where is", r"when is", r"why is", r"how is",
        r"simple\b", r"quick\b", r"easy\b", r"basic\b", r"general\b",
    ]
    
    def __init__(self):
        self.patterns = {
            TaskType.CODING: [re.compile(p, re.IGNORECASE) for p in self.CODING_PATTERNS],
            TaskType.COMPLEX_REASONING: [re.compile(p, re.IGNORECASE) for p in self.COMPLEX_REASONING_PATTERNS],
            TaskType.MULTIMODAL: [re.compile(p, re.IGNORECASE) for p in self.MULTIMODAL_PATTERNS],
            TaskType.SIMPLE_CHAT: [re.compile(p, re.IGNORECASE) for p in self.SIMPLE_CHAT_PATTERNS],
        }
        
        # Performance history tracking
        self.performance_history = {
            model_type: {"success_rate": 0.9, "avg_response_time": 2.0, "total_requests": 0}
            for model_type in ModelType
        }
    
    def analyze_task(self, user_input: str, context: Optional[List[Message]] = None) -> TaskType:
        """Analyze user input to determine task type."""
        input_lower = user_input.lower()
        
        scores = {
            TaskType.CODING: 0.0,
            TaskType.COMPLEX_REASONING: 0.0,
            TaskType.MULTIMODAL: 0.0,
            TaskType.SIMPLE_CHAT: 0.0,
            TaskType.UNKNOWN: 0.5,  # Default score
        }
        
        # Check patterns
        for task_type, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern.search(input_lower):
                    scores[task_type] += 0.1
                    # Multiple matches increase confidence
                    matches = len(pattern.findall(input_lower))
                    scores[task_type] += matches * 0.05
        
        # Check for explicit task indicators
        if any(word in input_lower for word in ["write code", "debug", "fix bug", "implement"]):
            scores[TaskType.CODING] += 0.3
        
        if any(word in input_lower for word in ["analyze", "explain", "compare", "evaluate"]):
            scores[TaskType.COMPLEX_REASONING] += 0.3
        
        if any(word in input_lower for word in ["image", "picture", "visual", "see this"]):
            scores[TaskType.MULTIMODAL] += 0.3
        
        # Short messages are likely simple chat
        if len(user_input.split()) < 10:
            scores[TaskType.SIMPLE_CHAT] += 0.2
        
        # Determine highest scoring task type
        best_task = max(scores.items(), key=lambda x: x[1])
        
        # If confidence is too low, mark as unknown
        if best_task[1] < 0.3:
            return TaskType.UNKNOWN
        
        return best_task[0]
    
    def update_performance(self, model_type: ModelType, success: bool, response_time: float):
        """Update performance history for a model."""
        history = self.performance_history[model_type]
        history["total_requests"] += 1
        
        # Update success rate (moving average)
        current_success_rate = history["success_rate"]
        new_success = 1.0 if success else 0.0
        history["success_rate"] = 0.9 * current_success_rate + 0.1 * new_success
        
        # Update response time (moving average)
        current_avg_time = history["avg_response_time"]
        history["avg_response_time"] = 0.9 * current_avg_time + 0.1 * response_time


class ModelRouter:
    """Routes tasks to appropriate models based on analysis."""
    
    def __init__(self, openrouter_client: OpenRouterClient):
        self.client = openrouter_client
        self.analyzer = TaskAnalyzer()
        
        # Default routing map (can be overridden by learning)
        self.routing_map = {
            TaskType.SIMPLE_CHAT: ModelType.GEMINI_FLASH,
            TaskType.CODING: ModelType.DEEPSEEK,
            TaskType.COMPLEX_REASONING: ModelType.MIMO,
            TaskType.MULTIMODAL: ModelType.GEMINI_PRO,
            TaskType.UNKNOWN: ModelType.QWEN,
        }
        
        # Cost-performance optimization weights
        self.weights = {
            "cost": 0.4,
            "speed": 0.3,
            "accuracy": 0.3,
        }
    
    async def route_task(
        self,
        user_input: str,
        context: Optional[List[Message]] = None,
        force_model: Optional[ModelType] = None,
    ) -> RoutingDecision:
        """Route a task to the appropriate model."""
        start_time = time.time()
        
        # If model is forced, use it
        if force_model:
            task_type = self.analyzer.analyze_task(user_input, context)
            capabilities = self.client.get_model_capabilities(force_model)
            
            return RoutingDecision(
                model_type=force_model,
                task_type=task_type,
                confidence=1.0,
                reasoning=f"Model forced by user: {force_model.value}",
                estimated_cost=self._estimate_cost(user_input, force_model),
                estimated_tokens=self.client.estimate_tokens(user_input),
            )
        
        # Analyze task
        task_type = self.analyzer.analyze_task(user_input, context)
        
        # Get candidate models for this task type
        candidate_models = self._get_candidate_models(task_type)
        
        # Evaluate candidates
        best_model, confidence, reasoning = self._evaluate_candidates(
            candidate_models, user_input, task_type
        )
        
        decision_time = time.time() - start_time
        
        return RoutingDecision(
            model_type=best_model,
            task_type=task_type,
            confidence=confidence,
            reasoning=reasoning,
            estimated_cost=self._estimate_cost(user_input, best_model),
            estimated_tokens=self.client.estimate_tokens(user_input),
        )
    
    def _get_candidate_models(self, task_type: TaskType) -> List[ModelType]:
        """Get candidate models for a task type."""
        primary_model = self.routing_map[task_type]
        candidates = [primary_model]
        
        # Add alternatives based on task type
        if task_type == TaskType.CODING:
            alternatives = [ModelType.QWEN, ModelType.MIMO]
        elif task_type == TaskType.COMPLEX_REASONING:
            alternatives = [ModelType.GEMINI_PRO, ModelType.QWEN]
        elif task_type == TaskType.SIMPLE_CHAT:
            alternatives = [ModelType.QWEN, ModelType.DEEPSEEK]
        else:  # MULTIMODAL or UNKNOWN
            alternatives = [ModelType.GEMINI_FLASH, ModelType.QWEN]
        
        # Filter out duplicates and add alternatives
        for alt in alternatives:
            if alt not in candidates:
                candidates.append(alt)
        
        return candidates
    
    def _evaluate_candidates(
        self, candidates: List[ModelType], user_input: str, task_type: TaskType
    ) -> Tuple[ModelType, float, str]:
        """Evaluate candidate models and select the best one."""
        if len(candidates) == 1:
            return candidates[0], 0.9, f"Only candidate for {task_type.value}"
        
        scores = {}
        reasoning_parts = []
        
        for model in candidates:
            score = 0.0
            caps = self.client.get_model_capabilities(model)
            perf = self.analyzer.performance_history[model]
            
            # Cost score (lower is better)
            cost_score = 1.0 - min(caps.cost_per_token / 5.0, 1.0)
            score += cost_score * self.weights["cost"]
            
            # Speed score
            speed_score = caps.speed * (1.0 / max(perf["avg_response_time"], 0.1))
            score += speed_score * self.weights["speed"]
            
            # Accuracy score
            accuracy_score = perf["success_rate"]
            
            # Task-specific capability adjustment
            if task_type == TaskType.CODING:
                accuracy_score *= caps.coding_strength
            elif task_type == TaskType.COMPLEX_REASONING:
                accuracy_score *= caps.reasoning_strength
            
            score += accuracy_score * self.weights["accuracy"]
            
            scores[model] = score
            
            reasoning_parts.append(
                f"{model.value}: cost={caps.cost_per_token:.2f}, "
                f"coding={caps.coding_strength:.1f}, "
                f"reasoning={caps.reasoning_strength:.1f}, "
                f"speed={caps.speed:.1f}"
            )
        
        # Select best model
        best_model = max(scores.items(), key=lambda x: x[1])
        confidence = best_model[1] / max(scores.values()) if max(scores.values()) > 0 else 0.5
        
        reasoning = f"Selected {best_model[0].value} for {task_type.value}. "
        reasoning += f"Candidates: {'; '.join(reasoning_parts)}"
        
        return best_model[0], confidence, reasoning
    
    def _estimate_cost(self, user_input: str, model_type: ModelType) -> float:
        """Estimate cost for processing input with a model."""
        caps = self.client.get_model_capabilities(model_type)
        tokens = self.client.estimate_tokens(user_input)
        
        # Estimate: input tokens * cost per token (simplified)
        estimated_cost = (tokens / 1_000_000) * caps.cost_per_token
        return estimated_cost
    
    def learn_from_feedback(
        self,
        model_type: ModelType,
        task_type: TaskType,
        success: bool,
        response_time: float,
        user_satisfaction: float,  # 0-1 scale
    ):
        """Learn from feedback to improve routing decisions."""
        # Update performance history
        self.analyzer.update_performance(model_type, success, response_time)
        
        # Adjust routing map based on success
        if success and user_satisfaction > 0.7:
            # This model performed well for this task type
            current_best = self.routing_map.get(task_type)
            # Guard against missing entries – ``current_best`` may be ``None``
            # or a model that is not yet present in ``performance_history``.
            if current_best is not None and current_best in self.analyzer.performance_history:
                # Only compare when we have performance data for *both* models.
                if model_type in self.analyzer.performance_history:
                    perf_current = self.analyzer.performance_history[current_best]
                    perf_new = self.analyzer.performance_history[model_type]

                    if (
                        perf_new["success_rate"] > perf_current["success_rate"] + 0.1
                        and perf_new["avg_response_time"] < perf_current["avg_response_time"]
                    ):
                        self.routing_map[task_type] = model_type
                        print(f"Updated routing: {task_type.value} -> {model_type.value}")
            # If ``current_best`` is ``None`` we simply adopt the new model –
            # this handles the situation where a new ``TaskType`` appears.
            elif current_best is None:
                self.routing_map[task_type] = model_type
                print(f"Routing map initialised: {task_type.value} -> {model_type.value}")
        
        # Adjust weights based on user satisfaction
        if user_satisfaction < 0.5:
            # User not satisfied, adjust weights
            if response_time > 5.0:  # Slow response
                self.weights["speed"] = min(self.weights["speed"] + 0.1, 0.5)
                self.weights["cost"] = max(self.weights["cost"] - 0.05, 0.2)
            elif response_time < 1.0:  # Fast but poor quality
                self.weights["accuracy"] = min(self.weights["accuracy"] + 0.1, 0.5)
                self.weights["speed"] = max(self.weights["speed"] - 0.05, 0.2)
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        stats = {
            "routing_map": {k.value: v.value for k, v in self.routing_map.items()},
            "weights": self.weights,
            "performance_history": {
                k.value: v for k, v in self.analyzer.performance_history.items()
            },
        }
        return stats
    
    async def self_improve(self):
        """Self-improvement routine to optimize routing."""
        # This could be enhanced to analyze historical data
        # and make more sophisticated adjustments
        
        print("Running self-improvement routine...")
        
        # Simple adjustment: if a model has poor performance for its primary task,
        # consider alternatives
        for task_type, current_model in self.routing_map.items():
            perf = self.analyzer.performance_history[current_model]
            
            if perf["success_rate"] < 0.6 and perf["total_requests"] > 10:
                # Look for alternative
                candidates = self._get_candidate_models(task_type)
                if len(candidates) > 1:
                    alternative = candidates[1]  # Second best
                    print(f"Considering switch: {task_type.value} from {current_model.value} to {alternative.value}")
        
        print("Self-improvement complete.")


# Helper function for quick routing
async def route_and_execute(
    router: ModelRouter,
    user_input: str,
    system_prompt: str = "You are a helpful AI assistant.",
    context: Optional[List[Message]] = None,
    stream: bool = False,
) -> Tuple[RoutingDecision, str]:
    """Route task and execute in one call."""
    from src.models.openrouter_client import create_messages
    
    # Route the task
    decision = await router.route_task(user_input, context)
    print(f"Routing decision: {decision.model_type.value} for {decision.task_type.value} (confidence: {decision.confidence:.2f})")
    print(f"Reasoning: {decision.reasoning}")
    
    # Prepare messages
    if context:
        messages = context
    else:
        messages = create_messages(system_prompt, user_input)
    
    # Execute with selected model
    client = OpenRouterClient()
    
    try:
        if stream:
            response_parts = []
            async for chunk in client.chat_completion_stream(
                messages=messages,
                model_type=decision.model_type,
            ):
                response_parts.append(chunk)
                print(chunk, end="", flush=True)
            
            response = "".join(response_parts)
            print()  # New line after streaming
        else:
            response_obj = await client.chat_completion(
                messages=messages,
                model_type=decision.model_type,
            )
            response = response_obj.choices[0]["message"]["content"]
        
        return decision, response
        
    finally:
        await client.close()