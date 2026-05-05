"""Chat router with context assembly, summarization, and tag-based retrieval."""
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.models.openrouter_client import OpenRouterClient, Message, ModelType
from src.memory.sqlite_store import SQLiteMemoryStore, SessionManager
from src.memory.vector_store import VectorMemoryStore
from src.utils.config import config
from src.processors.file_processor import FileProcessor


@dataclass
class ChatContext:
    """Represents assembled chat context."""
    system_prompt: str
    recent_summaries: List[Dict[str, str]]
    tag_matched_messages: List[Dict[str, Any]]
    assembled_messages: List[Message]


class ChatRouter:
    """Routes chat requests with smart context assembly."""
    
    def __init__(self, memory_store: Optional[SQLiteMemoryStore] = None, vector_store: Optional[VectorMemoryStore] = None):
        self.memory_store = memory_store or SQLiteMemoryStore()
        self.vector_store = vector_store or VectorMemoryStore()
        self.session_manager = SessionManager(self.memory_store)
        self.client = None
        self.current_session_id = self.session_manager.current_session_id
    
    def initialize_client(self):
        """Initialize OpenRouter client."""
        self.client = OpenRouterClient()
    
    async def chat(
        self,
        user_message: str,
        session_id: Optional[str] = None,
        model_override: Optional[str] = None,
        use_tags: bool = True,
        use_summaries: bool = True,
    ) -> Dict[str, Any]:
        """Process chat message with context assembly."""
        if self.client is None:
            self.initialize_client()
        
        # Use provided session or current session
        effective_session_id = session_id or self.current_session_id
        
        # Save raw user message
        user_msg_id = self.memory_store.save_message(
            session_id=effective_session_id,
            role="user",
            content_raw=user_message,
            model_id=None,
            tokens_used=0,
        )
        
        # Add to vector store
        self.vector_store.add_message(
            session_id=effective_session_id,
            role="user",
            content=user_message,
            message_id=user_msg_id
        )
        
        # Extract tags from user message
        tags = []
        if use_tags:
            tag_model_id = config.settings.tag_extraction_model
            if tag_model_id:
                tags = await self.client.extract_tags(user_message, tag_model_id)
            else:
                tags = await self.client.extract_tags(user_message, use_heuristic=True)
            
            # Update message with tags
            if tags:
                self.memory_store.update_message_tags(user_msg_id, tags)
        
        # Assemble context
        context = await self._assemble_context(
            session_id=effective_session_id,
            user_message=user_message,
            tags=tags,
            use_summaries=use_summaries,
        )
        
        # Determine which model to use
        model_type = await self._select_model(
            user_message=user_message,
            context=context,
            model_override=model_override,
        )
        
        # Get assistant response
        assistant_response = await self._get_assistant_response(
            context=context,
            model_type=model_type,
        )
        
        # Save assistant message
        assistant_msg_id = self.memory_store.save_message(
            session_id=effective_session_id,
            role="assistant",
            content_raw=assistant_response["content"],
            model_id=assistant_response["model_id"],
            tokens_used=assistant_response.get("tokens_used", 0),
        )
        
        # Add to vector store
        self.vector_store.add_message(
            session_id=effective_session_id,
            role="assistant",
            content=assistant_response["content"],
            message_id=assistant_msg_id
        )
        
        # Summarize both messages asynchronously
        if use_summaries:
            asyncio.create_task(self._summarize_messages(user_msg_id, assistant_msg_id))
        
        return {
            "response": assistant_response["content"],
            "model": assistant_response["model_id"],
            "session_id": effective_session_id,
            "tokens_used": assistant_response.get("tokens_used", 0),
            "tags": tags,
        }
    
    async def _assemble_context(
        self,
        session_id: str,
        user_message: str,
        tags: List[str],
        use_summaries: bool = True,
    ) -> ChatContext:
        """Assemble chat context from summaries and tag-matched messages."""
        context_messages = []
        
        # Get system prompt from config
        system_prompt = config.settings.system_prompt
        
        # Add system prompt
        context_messages.append(Message(role="system", content=system_prompt))
        
        # Check for potential file paths in user message
        extracted_files_context = []
        checked_paths = set()
        
        # Regex to find absolute/relative paths and filenames with specific extensions
        path_pattern = r'(?:/[a-zA-Z0-9_.-]+)+/[a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+'
        file_pattern = r'[a-zA-Z0-9_.-]+\.(?:py|txt|pdf|md|csv|json|js|ts|tsx|html|css|rs)'
        
        potential_paths = re.findall(path_pattern, user_message) + re.findall(file_pattern, user_message)
        
        for path_str in potential_paths:
            if path_str in checked_paths: continue
            checked_paths.add(path_str)
            try:
                p = Path(path_str)
                # Ensure it's a file and not too large (e.g. limit to 1MB to avoid blowing up context)
                if p.exists() and p.is_file():
                    if p.stat().st_size < 1024 * 1024:  # 1MB limit
                        content = FileProcessor.process_file(str(p))
                        extracted_files_context.append(f"--- Contents of {path_str} ---\n{content}\n--- End of {path_str} ---")
            except Exception:
                pass
                
        if extracted_files_context:
            context_messages.append(
                Message(role="system", content="The user referenced the following files in their message:\n\n" + "\n\n".join(extracted_files_context))
            )
        
        recent_summaries = []
        if use_summaries:
            # Fetch unique summaries to provide broad context without confusing the model
            cursor = self.memory_store.connection.cursor()
            cursor.execute("""
            SELECT DISTINCT content_summary
            FROM (
                SELECT content_summary, MIN(created_at) as first_created
                FROM messages
                WHERE session_id = ? AND content_summary IS NOT NULL
                GROUP BY content_summary
                ORDER BY first_created DESC
                LIMIT 3
            )
            ORDER BY first_created ASC
            """, (session_id,))
            rows = cursor.fetchall()
            summaries = [row["content_summary"] for row in rows]
            recent_summaries = [{"content_summary": s} for s in summaries]
            
            if summaries:
                summary_text = "\n".join(f"- {s}" for s in summaries)
                context_messages.append(
                    Message(role="system", content=f"Summary of older conversation:\n{summary_text}")
                )
        
        tag_matched_messages = []
        if tags:
            # Get messages matching tags
            matched = self.memory_store.get_messages_by_tags(tags, session_id, limit=3)
            tag_matched_messages = matched
            
            # Add tag-matched messages to context
            related_text = "\n".join([m["content_summary"] or m["content_raw"] for m in matched if m["content_raw"] != user_message])
            if related_text:
                context_messages.append(
                    Message(role="system", content=f"Related past context based on keywords:\n{related_text}")
                )
                
        # Add recent raw messages (last 4 messages = 2 turns) to keep conversational style
        recent_raw = self.memory_store.get_messages(session_id, limit=4)
        for msg in recent_raw:
            # The current user message is already in the db, don't add it yet
            if msg["content_raw"] != user_message:
                context_messages.append(Message(role=msg["role"], content=msg["content_raw"]))
        
        # Add current user message
        context_messages.append(Message(role="user", content=user_message))
        
        # Search vector store for similar past context
        similar_past = self.vector_store.search_similar_messages(query=user_message, limit=3)
        if similar_past:
            vector_context_texts = []
            for item in similar_past:
                # Ensure we don't duplicate the current exact message
                if item["content"] != user_message:
                    vector_context_texts.append(f"[{item['metadata'].get('role', 'unknown')}]: {item['content']}")
            
            if vector_context_texts:
                vector_context = "\n".join(vector_context_texts)
                context_messages.insert(-1, Message(role="system", content=f"Relevant past conversation snippets retrieved from memory:\n{vector_context}\n\nSYSTEM INSTRUCTION: You MUST use these retrieved memories to answer the user. Do NOT claim that you lack memory or cannot retain personal details across sessions, as these snippets are your explicit memory."))
        
        return ChatContext(
            system_prompt=system_prompt,
            recent_summaries=recent_summaries,
            tag_matched_messages=tag_matched_messages,
            assembled_messages=context_messages,
        )
    
    async def _select_model(
        self,
        user_message: str,
        context: ChatContext,
        model_override: Optional[str] = None,
    ) -> ModelType:
        """Select appropriate model based on message and context."""
        if model_override:
            # Map override to ModelType
            override_map = {
                "qwen": ModelType.QWEN,
                "gemini-flash": ModelType.GEMINI_FLASH,
                "mimo": ModelType.MIMO,
                "deepseek": ModelType.DEEPSEEK,
                "gemini-pro": ModelType.GEMINI_PRO,
            }
            return override_map.get(model_override.lower(), ModelType.GEMINI_FLASH)
        
        # Use default chat model from config
        default_model = config.settings.default_chat_model
        model_map = {
            "gemini-2.5-flash-lite": ModelType.GEMINI_FLASH,
            "qwen-2.5-32b-instruct": ModelType.QWEN,
            "mimo-v2-pro": ModelType.MIMO,
            "deepseek-v3.2": ModelType.DEEPSEEK,
            "gemini-3.1-pro": ModelType.GEMINI_PRO,
        }
        
        return model_map.get(default_model, ModelType.GEMINI_FLASH)
    
    async def _get_assistant_response(
        self,
        context: ChatContext,
        model_type: ModelType,
    ) -> Dict[str, Any]:
        """Get assistant response from OpenRouter."""
        try:
            response = await self.client.chat_completion(
                messages=context.assembled_messages,
                model_type=model_type,
            )
            
            # Extract response content
            if response.choices and len(response.choices) > 0:
                choice = response.choices[0]
                if "message" in choice and "content" in choice["message"]:
                    content = choice["message"]["content"]
                else:
                    content = str(choice)
            else:
                content = "No response generated."
            
            # Get token usage
            tokens_used = 0
            if response.usage:
                tokens_used = response.usage.total_tokens
            
            return {
                "content": content,
                "model_id": config.settings.model_gemini_flash if model_type == ModelType.GEMINI_FLASH else "",
                "tokens_used": tokens_used,
            }
            
        except Exception as e:
            print(f"Error getting assistant response: {e}")
            return {
                "content": f"Error: {str(e)}",
                "model_id": "",
                "tokens_used": 0,
            }
    
    async def _summarize_messages(self, user_msg_id: str, assistant_msg_id: str):
        """Summarize messages asynchronously."""
        try:
            # Get messages
            cursor = self.memory_store.connection.cursor()
            cursor.execute(
                "SELECT content_raw FROM messages WHERE id IN (?, ?)",
                (user_msg_id, assistant_msg_id)
            )
            rows = cursor.fetchall()
            
            if len(rows) == 2:
                user_content = rows[0]["content_raw"]
                assistant_content = rows[1]["content_raw"]
                
                # Combine for summarization
                combined = f"User: {user_content}\nAssistant: {assistant_content}"
                
                # Summarize
                summary = await self.client.summarize_content(
                    content=combined,
                    max_tokens=config.settings.summary_max_tokens,
                    model_id="openai/gpt-oss-120b",
                )
                
                # Update both messages with same summary (or split as needed)
                self.memory_store.update_message_summary(user_msg_id, summary)
                self.memory_store.update_message_summary(assistant_msg_id, summary)
                
        except Exception as e:
            print(f"Error summarizing messages: {e}")
    
    def get_session_history(
        self,
        session_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get chat history for session."""
        effective_session_id = session_id or self.current_session_id
        return self.memory_store.get_messages(effective_session_id, limit)
    
    def new_session(self) -> str:
        """Start a new chat session."""
        self.current_session_id = self.session_manager.new_session()
        return self.current_session_id
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for current session."""
        return self.session_manager.get_session_stats()
    
    def close(self):
        """Cleanup resources."""
        if self.memory_store:
            self.memory_store.close()
    
    async def __aenter__(self):
        self.initialize_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Helper function for simple chat
async def simple_chat(user_message: str, session_id: Optional[str] = None) -> str:
    """Simple chat interface."""
    async with ChatRouter() as router:
        result = await router.chat(user_message, session_id)
        return result["response"]