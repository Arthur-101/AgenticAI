#!/usr/bin/env python3
"""
Minimal Python backend for Tauri integration.
Communicates via stdin/stdout JSON-RPC instead of HTTP.
"""

import sys
import json
import traceback
from typing import Dict, Any, Optional
import os
import asyncio

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.memory.sqlite_store import SQLiteMemoryStore, SessionManager
from src.controller.chat_router import ChatRouter
from src.utils.config import config


class EmbeddedBackend:
    """Minimal backend that handles JSON-RPC requests via stdin/stdout."""
    
    def __init__(self):
        self.memory = SQLiteMemoryStore(db_path="data/agenticai.db")
        self.router = ChatRouter(
            memory_store=self.memory
        )
        print("INFO: Embedded backend initialized", file=sys.stderr)
    
    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a JSON-RPC request and return response."""
        try:
            method = request.get("method")
            params = request.get("params", {})
            
            if method == "chat":
                return await self._handle_chat(params)
            elif method == "health":
                return self._handle_health()
            elif method == "history":
                return self._handle_history(params)
            elif method == "new_session":
                return self._handle_new_session()
            elif method == "get_sessions":
                return self._handle_get_sessions()
            elif method == "delete_session":
                return self._handle_delete_session(params)
            elif method == "get_all_memories":
                return self._handle_get_all_memories()
            elif method == "update_memory":
                return self._handle_update_memory(params)
            else:
                return {
                    "jsonrpc": "2.0",
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                    "id": request.get("id")
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                    "data": traceback.format_exc()
                },
                "id": request.get("id")
            }
    
    async def _handle_chat(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chat request."""
        message = params.get("message", "")
        session_id = params.get("session_id")
        use_tags = params.get("use_tags", True)
        use_summaries = params.get("use_summaries", True)
        
        if not message:
            raise ValueError("Message is required")
        
        result = await self.router.chat(
            user_message=message,
            session_id=session_id,
            use_tags=use_tags,
            use_summaries=use_summaries
        )
        
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": params.get("request_id")
        }
    
    def _handle_health(self) -> Dict[str, Any]:
        """Handle health check."""
        return {
            "jsonrpc": "2.0",
            "result": {
                "status": "healthy",
                "router_initialized": True,
                "service": "agenticai-embedded"
            },
            "id": None
        }
    
    def _handle_history(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle history request."""
        session_id = params.get("session_id")
        limit = params.get("limit", 50)
        
        messages = self.memory.get_messages(
            session_id=session_id,
            limit=limit
        )
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "messages": messages
            },
            "id": params.get("request_id")
        }
    
    def _handle_new_session(self) -> Dict[str, Any]:
        """Handle new session creation."""
        session_id = self.router.new_session()
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "session_id": session_id
            },
            "id": None
        }

    def _handle_get_sessions(self) -> Dict[str, Any]:
        """Handle request to get all sessions."""
        sessions = self.memory.get_all_sessions()
        
        return {
            "jsonrpc": "2.0",
            "result": {
                "sessions": sessions
            },
            "id": None
        }

    def _handle_delete_session(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        success = self.memory.delete_session(session_id)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success},
            "id": params.get("request_id")
        }

    def _handle_get_all_memories(self) -> Dict[str, Any]:
        memories = self.memory.get_all_memories_with_tags()
        return {
            "jsonrpc": "2.0",
            "result": {"memories": memories},
            "id": None
        }

    def _handle_update_memory(self, params: Dict[str, Any]) -> Dict[str, Any]:
        message_id = params.get("message_id")
        content = params.get("content")
        success = self.memory.update_message_content(message_id, content)
        return {
            "jsonrpc": "2.0",
            "result": {"success": success},
            "id": params.get("request_id")
        }

async def main_async():
    """Async main entry point."""
    # Redirect standard output to stderr to prevent random prints from breaking JSON-RPC
    original_stdout = sys.stdout
    sys.stdout = sys.stderr
    
    backend = EmbeddedBackend()
    
    # Ensure original stdout is line-buffered
    original_stdout.reconfigure(line_buffering=True)
    
    print("INFO: Embedded backend ready, waiting for JSON-RPC requests...", file=sys.stderr)
    
    loop = asyncio.get_event_loop()
    
    while True:
        # Read from stdin without blocking the asyncio event loop
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break
        if not line.strip():
            continue
            
        try:
            request = json.loads(line)
            # Await the processing so responses remain somewhat ordered
            response = await backend.process_request(request)
            print(json.dumps(response), file=original_stdout, flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error: Invalid JSON"
                },
                "id": None
            }
            print(json.dumps(error_response), file=original_stdout, flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": None
            }
            print(json.dumps(error_response), file=original_stdout, flush=True)


def main():
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()