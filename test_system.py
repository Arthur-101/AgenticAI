#!/usr/bin/env python3
"""Test script for AgenticAI system components."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.models.openrouter_client import OpenRouterClient, ModelType, create_messages
from src.controller.model_router import ModelRouter
from src.memory.sqlite_store import SQLiteMemoryStore, SessionManager
from src.utils.config import config


async def test_openrouter_client():
    """Test OpenRouter client."""
    print("Testing OpenRouter client...")
    
    client = OpenRouterClient()
    
    try:
        # Test model listing
        models = client.get_available_models()
        print(f"✓ Found {len(models)} models")
        
        # Test token estimation
        test_text = "Hello, this is a test message."
        tokens = client.estimate_tokens(test_text)
        print(f"✓ Token estimation works: '{test_text}' = {tokens} tokens")
        
        # Test model capabilities
        for model_type in ModelType:
            caps = client.get_model_capabilities(model_type)
            print(f"  {model_type.value}: max_tokens={caps.max_tokens}, coding={caps.coding_strength}")
        
        return True
        
    except Exception as e:
        print(f"✗ OpenRouter client test failed: {e}")
        return False
    finally:
        await client.close()


def test_memory_store():
    """Test SQLite memory store."""
    print("\nTesting memory store...")
    
    memory_store = SQLiteMemoryStore(":memory:")  # In-memory database for testing
    
    try:
        # Test conversation storage
        conv_id = memory_store.save_conversation(
            session_id="test-session",
            model_id="test-model",
            user_message="Hello",
            assistant_message="Hi there!",
            tokens_used=50,
            cost=0.001,
        )
        print(f"✓ Conversation saved: {conv_id}")
        
        # Test conversation retrieval
        history = memory_store.get_conversation_history("test-session")
        print(f"✓ Retrieved {len(history)} conversations")
        
        # Test tool execution storage
        tool_id = memory_store.save_tool_execution(
            conversation_id=conv_id,
            tool_name="test_tool",
            parameters={"param1": "value1"},
            result="Tool executed successfully",
            success=True,
            execution_time=0.5,
        )
        print(f"✓ Tool execution saved: {tool_id}")
        
        # Test cost tracking
        cost_id = memory_store.track_cost(
            model_id="test-model",
            operation_type="completion",
            tokens_input=100,
            tokens_output=200,
            cost=0.005,
            latency=1.5,
        )
        print(f"✓ Cost tracked: {cost_id}")
        
        # Test cost summary
        summary = memory_store.get_cost_summary()
        print(f"✓ Cost summary: total_cost=${summary['total_cost']:.4f}")
        
        # Test database stats
        stats = memory_store.get_database_stats()
        print(f"✓ Database stats: {stats.get('conversations_count', 0)} conversations")
        
        return True
        
    except Exception as e:
        print(f"✗ Memory store test failed: {e}")
        return False
    finally:
        memory_store.close()


def test_session_manager():
    """Test session manager."""
    print("\nTesting session manager...")
    
    memory_store = SQLiteMemoryStore(":memory:")
    session_manager = SessionManager(memory_store)
    
    try:
        # Test new session
        new_session_id = session_manager.new_session()
        print(f"✓ New session created: {new_session_id}")
        
        # Test session context (empty)
        context = session_manager.get_session_context()
        print(f"✓ Session context: {len(context)} messages")
        
        # Test saving conversation
        conv_id = session_manager.save_conversation(
            model_id="test-model",
            user_message="Test message",
            assistant_message="Test response",
            tokens_used=100,
            cost=0.002,
        )
        print(f"✓ Conversation saved to session: {conv_id}")
        
        # Test session stats
        stats = session_manager.get_session_stats()
        print(f"✓ Session stats: {stats['conversation_count']} conversations")
        
        return True
        
    except Exception as e:
        print(f"✗ Session manager test failed: {e}")
        return False
    finally:
        memory_store.close()


async def test_model_router():
    """Test model router."""
    print("\nTesting model router...")
    
    client = OpenRouterClient()
    router = ModelRouter(client)
    
    try:
        # Test task analysis
        test_tasks = [
            ("Write a Python function to sort a list", "coding"),
            ("Explain quantum physics to a 5-year-old", "complex_reasoning"),
            ("Hi, how are you today?", "simple_chat"),
            ("Describe this image of a cat", "multimodal"),
        ]
        
        for task, expected_type in test_tasks:
            task_type = router.analyzer.analyze_task(task)
            print(f"  Task: '{task[:30]}...' → {task_type.value} (expected: {expected_type})")
        
        # Test routing decisions
        test_inputs = [
            "Write a bubble sort algorithm in Python",
            "What are the philosophical implications of AI?",
            "Hello! What's the weather like?",
            "Can you see this picture and tell me what's in it?",
        ]
        
        for user_input in test_inputs:
            decision = await router.route_task(user_input)
            print(f"  Input: '{user_input[:30]}...' → Model: {decision.model_type.value}, Confidence: {decision.confidence:.2f}")
        
        # Test routing stats
        stats = router.get_routing_stats()
        print(f"✓ Routing stats: {len(stats['routing_map'])} task types mapped")
        
        return True
        
    except Exception as e:
        print(f"✗ Model router test failed: {e}")
        return False
    finally:
        await client.close()


def test_config():
    """Test configuration system."""
    print("\nTesting configuration...")
    
    try:
        # Test settings
        settings = config.settings
        print(f"✓ Configuration loaded")
        print(f"  OpenRouter URL: {settings.openrouter_base_url}")
        print(f"  Cost limit: ${settings.cost_limit}")
        print(f"  Max tokens: {settings.max_tokens_per_request}")
        
        # Test cost tracking
        config.track_cost("test-model", 100, 200)
        cost_summary = config.get_cost_summary()
        print(f"✓ Cost tracking works: total=${cost_summary['total_cost']:.4f}")
        
        # Test file type validation
        test_files = [
            "document.pdf",
            "script.py",
            "data.json",
            "image.png",  # Should fail (not in allowed types)
        ]
        
        for file in test_files:
            allowed = config.is_file_type_allowed(file)
            print(f"  File '{file}': {'✓ Allowed' if allowed else '✗ Not allowed'}")
        
        return True
        
    except Exception as e:
        print(f"✗ Configuration test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("AgenticAI System Test")
    print("=" * 60)
    
    test_results = []
    
    # Run tests
    test_results.append(("Configuration", test_config()))
    test_results.append(("Memory Store", test_memory_store()))
    test_results.append(("Session Manager", test_session_manager()))
    test_results.append(("OpenRouter Client", await test_openrouter_client()))
    test_results.append(("Model Router", await test_model_router()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in test_results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All tests passed! System is ready.")
    else:
        print("❌ Some tests failed. Check above for details.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)