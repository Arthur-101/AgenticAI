import sqlite3
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import uuid

from src.utils.config import config
from src.models.openrouter_client import ModelType, Message


class SQLiteMemoryStore:
    """SQLite-based memory storage for conversations, tools, and documents."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Create the SQLite connection.

        * If ``db_path`` is the sentinel ``":memory:"`` we open an
          in‑memory database (useful for tests).
        * Otherwise we treat ``db_path`` as a filesystem path, ensure the
          parent directory exists, and open the file‑based database.
        """
        raw_path = db_path or config.settings.sqlite_db_path
        # Detect the explicit in‑memory sentinel (allow surrounding whitespace)
        if isinstance(raw_path, str) and raw_path.strip() == ":memory:":
            self.connection = sqlite3.connect(":memory:")
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(raw_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._initialize_database()

    # -----------------------------------------------------------------
    # Helper that always commits after a write operation (reduces boiler‑plate)
    # -----------------------------------------------------------------
    def _execute(self, sql: str, params: tuple = ()):  # pragma: no cover – simple helper
        cur = self.connection.cursor()
        cur.execute(sql, params)
        self.connection.commit()
        return cur

    
    
    def _initialize_database(self):
        """Initialize database with required tables."""
        cursor = self.connection.cursor()
        
        # Create conversations table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            model_id TEXT,
            user_message TEXT,
            assistant_message TEXT,
            tokens_used INTEGER,
            cost REAL,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create tool_executions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_executions (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            tool_name TEXT,
            parameters TEXT,
            result TEXT,
            success INTEGER,
            execution_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations (id)
        )
        """)
        
        # Create documents table (for RAG)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            content TEXT,
            source TEXT,
            embedding_id TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create cost_tracking table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_tracking (
            id TEXT PRIMARY KEY,
            model_id TEXT,
            operation_type TEXT,
            tokens_input INTEGER,
            tokens_output INTEGER,
            cost REAL,
            latency REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create messages table for chat with summaries and tags
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            role TEXT NOT NULL,
            content_raw TEXT NOT NULL,
            content_summary TEXT,
            tags_json TEXT,
            model_id TEXT,
            tokens_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES conversations (id) ON DELETE CASCADE
        )
        """)
        
        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tools_conversation ON tool_executions(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_model ON cost_tracking(model_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_created ON cost_tracking(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_tags ON messages(tags_json)")
        
        self.connection.commit()
    
    def save_conversation(
        self,
        session_id: str,
        model_id: str,
        user_message: str,
        assistant_message: str,
        tokens_used: int = 0,
        cost: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a conversation to memory."""
        conversation_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO conversations 
            (id, session_id, model_id, user_message, assistant_message, tokens_used, cost, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                session_id,
                model_id,
                user_message,
                assistant_message,
                tokens_used,
                cost,
                json.dumps(metadata or {}),
            ),
        )
        return conversation_id
    
    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a session."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT id, model_id, user_message, assistant_message, tokens_used, cost, metadata, created_at
        FROM conversations
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """, (session_id, limit, offset))
        
        rows = cursor.fetchall()
        conversations = []
        
        for row in rows:
            conversations.append({
                "id": row["id"],
                "model_id": row["model_id"],
                "user_message": row["user_message"],
                "assistant_message": row["assistant_message"],
                "tokens_used": row["tokens_used"],
                "cost": row["cost"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "created_at": row["created_at"],
            })
        
        return conversations
    
    def save_tool_execution(
        self,
        conversation_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        result: str,
        success: bool = True,
        execution_time: float = 0.0,
    ) -> str:
        """Save tool execution record."""
        tool_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO tool_executions
            (id, conversation_id, tool_name, parameters, result, success, execution_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool_id,
                conversation_id,
                tool_name,
                json.dumps(parameters),
                result,
                1 if success else 0,
                execution_time,
            ),
        )
        return tool_id
    
    def get_tool_executions(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get tool executions for a conversation."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT id, tool_name, parameters, result, success, execution_time, created_at
        FROM tool_executions
        WHERE conversation_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """, (conversation_id, limit))
        
        rows = cursor.fetchall()
        executions = []
        
        for row in rows:
            executions.append({
                "id": row["id"],
                "tool_name": row["tool_name"],
                "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
                "result": row["result"],
                "success": bool(row["success"]),
                "execution_time": row["execution_time"],
                "created_at": row["created_at"],
            })
        
        return executions
    
    def save_document(
        self,
        content: str,
        source: str,
        embedding_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save a document for RAG."""
        document_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO documents
            (id, content, source, embedding_id, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                document_id,
                content,
                source,
                embedding_id,
                json.dumps(metadata or {}),
            ),
        )
        return document_id
    
    def search_documents(
        self,
        query: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search documents by content or source."""
        cursor = self.connection.cursor()
        
        if query:
            # Simple text search (can be enhanced with FTS)
            cursor.execute("""
            SELECT id, content, source, embedding_id, metadata, created_at
            FROM documents
            WHERE content LIKE ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """, (f"%{query}%", limit, offset))
        elif source:
            cursor.execute("""
            SELECT id, content, source, embedding_id, metadata, created_at
            FROM documents
            WHERE source = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """, (source, limit, offset))
        else:
            cursor.execute("""
            SELECT id, content, source, embedding_id, metadata, created_at
            FROM documents
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """, (limit, offset))
        
        rows = cursor.fetchall()
        documents = []
        
        for row in rows:
            documents.append({
                "id": row["id"],
                "content": row["content"],
                "source": row["source"],
                "embedding_id": row["embedding_id"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "created_at": row["created_at"],
            })
        
        return documents
    
    def track_cost(
        self,
        model_id: str,
        operation_type: str,
        tokens_input: int,
        tokens_output: int,
        cost: float,
        latency: float,
    ) -> str:
        """Track cost usage."""
        cost_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO cost_tracking
            (id, model_id, operation_type, tokens_input, tokens_output, cost, latency)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cost_id,
                model_id,
                operation_type,
                tokens_input,
                tokens_output,
                cost,
                latency,
            ),
        )
        return cost_id
    
    def get_cost_summary(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get cost summary for time period."""
        cursor = self.connection.cursor()
        
        query = "SELECT model_id, SUM(tokens_input) as total_input, SUM(tokens_output) as total_output, SUM(cost) as total_cost FROM cost_tracking"
        conditions = []
        params = []
        
        if start_date:
            conditions.append("created_at >= ?")
            params.append(start_date)
        
        if end_date:
            conditions.append("created_at <= ?")
            params.append(end_date)
        
        if model_id:
            conditions.append("model_id = ?")
            params.append(model_id)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " GROUP BY model_id"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        summary = {
            "total_cost": 0.0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "by_model": {},
        }
        
        for row in rows:
            model = row["model_id"]
            summary["by_model"][model] = {
                "cost": row["total_cost"] or 0.0,
                "input_tokens": row["total_input"] or 0,
                "output_tokens": row["total_output"] or 0,
            }
            summary["total_cost"] += row["total_cost"] or 0.0
            summary["total_input_tokens"] += row["total_input"] or 0
            summary["total_output_tokens"] += row["total_output"] or 0
        
        return summary
    
    def get_recent_conversations(
        self,
        days: int = 7,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent conversations across all sessions."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT session_id, model_id, user_message, assistant_message, tokens_used, cost, created_at
        FROM conversations
        WHERE created_at >= datetime('now', ?)
        ORDER BY created_at DESC
        LIMIT ?
        """, (f"-{days} days", limit))
        
        rows = cursor.fetchall()
        conversations = []
        
        for row in rows:
            conversations.append({
                "session_id": row["session_id"],
                "model_id": row["model_id"],
                "user_message": row["user_message"][:100] + "..." if len(row["user_message"]) > 100 else row["user_message"],
                "assistant_message": row["assistant_message"][:100] + "..." if len(row["assistant_message"]) > 100 else row["assistant_message"],
                "tokens_used": row["tokens_used"],
                "cost": row["cost"],
                "created_at": row["created_at"],
            })
        
        return conversations
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old data to save space."""
        deleted_rows = 0
        
        # Delete old conversations
        cursor = self._execute("""
        DELETE FROM conversations
        WHERE created_at < datetime('now', ?)
        """, (f"-{days_to_keep} days",))
        deleted_rows += cursor.rowcount
        
        # Delete old tool executions
        cursor = self._execute("""
        DELETE FROM tool_executions
        WHERE created_at < datetime('now', ?)
        """, (f"-{days_to_keep} days",))
        deleted_rows += cursor.rowcount
        
        # Delete old cost tracking
        cursor = self._execute("""
        DELETE FROM cost_tracking
        WHERE created_at < datetime('now', ?)
        """, (f"-{days_to_keep} days",))
        deleted_rows += cursor.rowcount
        
        # Delete old messages
        cursor = self._execute("""
        DELETE FROM messages
        WHERE created_at < datetime('now', ?)
        """, (f"-{days_to_keep} days",))
        deleted_rows += cursor.rowcount
        
        return deleted_rows
    
    def save_message(
        self,
        session_id: str,
        role: str,
        content_raw: str,
        content_summary: Optional[str] = None,
        tags: Optional[List[str]] = None,
        model_id: Optional[str] = None,
        tokens_used: int = 0,
    ) -> str:
        """Save a chat message with optional summary and tags."""
        message_id = str(uuid.uuid4())
        self._execute(
            """
            INSERT INTO messages
            (id, session_id, role, content_raw, content_summary, tags_json, model_id, tokens_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message_id,
                session_id,
                role,
                content_raw,
                content_summary,
                json.dumps(tags or []),
                model_id,
                tokens_used,
            ),
        )
        return message_id
    
    def update_message_summary(
        self,
        message_id: str,
        content_summary: str,
    ) -> None:
        """Update the summary for an existing message."""
        self._execute(
            """
            UPDATE messages
            SET content_summary = ?
            WHERE id = ?
            """,
            (content_summary, message_id),
        )
    
    def update_message_tags(
        self,
        message_id: str,
        tags: List[str],
    ) -> None:
        """Update tags for an existing message."""
        self._execute(
            """
            UPDATE messages
            SET tags_json = ?
            WHERE id = ?
            """,
            (json.dumps(tags), message_id),
        )
    
    def get_messages(
        self,
        session_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get messages for a session."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT id, role, content_raw, content_summary, tags_json, model_id, tokens_used, created_at
        FROM messages
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
        """, (session_id, limit, offset))
        
        rows = cursor.fetchall()
        messages = []
        
        for row in rows:
            messages.append({
                "id": row["id"],
                "role": row["role"],
                "content_raw": row["content_raw"],
                "content_summary": row["content_summary"],
                "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
                "model_id": row["model_id"],
                "tokens_used": row["tokens_used"],
                "created_at": row["created_at"],
            })
        
        return messages
    
    def get_messages_by_tags(
        self,
        tags: List[str],
        session_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get messages that match any of the given tags."""
        cursor = self.connection.cursor()
        
        # Build tag matching query
        tag_conditions = []
        params = []
        
        for tag in tags:
            tag_conditions.append("tags_json LIKE ?")
            params.append(f'%"{tag}"%')
        
        query = """
        SELECT id, session_id, role, content_raw, content_summary, tags_json, model_id, tokens_used, created_at
        FROM messages
        WHERE ("""
        query += " OR ".join(tag_conditions)
        query += ")"
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        messages = []
        for row in rows:
            messages.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content_raw": row["content_raw"],
                "content_summary": row["content_summary"],
                "tags": json.loads(row["tags_json"]) if row["tags_json"] else [],
                "model_id": row["model_id"],
                "tokens_used": row["tokens_used"],
                "created_at": row["created_at"],
            })
        
        return messages
    
    def get_recent_summaries(
        self,
        session_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get recent message summaries for context building."""
        cursor = self.connection.cursor()
        cursor.execute("""
        SELECT role, content_summary
        FROM messages
        WHERE session_id = ? AND content_summary IS NOT NULL
        ORDER BY created_at DESC
        LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        summaries = []
        
        for row in rows:
            summaries.append({
                "role": row["role"],
                "content_summary": row["content_summary"],
            })
        
        return summaries
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        cursor = self.connection.cursor()
        
        stats = {}
        
        # Count tables
        tables = ["conversations", "tool_executions", "documents", "cost_tracking", "messages"]
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[f"{table}_count"] = cursor.fetchone()["count"]
        
        # Database size
        cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        stats["database_size_bytes"] = cursor.fetchone()["size"]
        
        # Most used model
        cursor.execute("""
        SELECT model_id, COUNT(*) as count
        FROM conversations
        GROUP BY model_id
        ORDER BY count DESC
        LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            stats["most_used_model"] = row["model_id"]
            stats["most_used_model_count"] = row["count"]
        
        return stats
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Helper class for session management
class SessionManager:
    """Manages conversation sessions."""
    
    def __init__(self, memory_store: SQLiteMemoryStore):
        self.memory_store = memory_store
        self.current_session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
    
    def new_session(self) -> str:
        """Start a new session."""
        self.current_session_id = str(uuid.uuid4())
        self.session_start = datetime.now()
        return self.current_session_id
    
    def get_session_context(
        self,
        max_messages: int = 10,
        max_tokens: int = 2000,
    ) -> List[Message]:
        """Get conversation context for current session."""
        from src.models.openrouter_client import Message
        
        conversations = self.memory_store.get_conversation_history(
            self.current_session_id,
            limit=max_messages * 2,  # Get more to filter by tokens
        )
        
        messages = []
        total_tokens = 0
        
        # Add conversations in chronological order (oldest first)
        for conv in reversed(conversations):
            # Estimate tokens (simplified)
            user_tokens = len(conv["user_message"].split())
            assistant_tokens = len(conv["assistant_message"].split())
            message_tokens = user_tokens + assistant_tokens + 20  # Add overhead
            
            if total_tokens + message_tokens > max_tokens:
                break
            
            messages.append(Message(role="user", content=conv["user_message"]))
            messages.append(Message(role="assistant", content=conv["assistant_message"]))
            total_tokens += message_tokens
        
        return messages
    
    def save_conversation(
        self,
        model_id: str,
        user_message: str,
        assistant_message: str,
        tokens_used: int = 0,
        cost: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Save conversation to current session."""
        return self.memory_store.save_conversation(
            session_id=self.current_session_id,
            model_id=model_id,
            user_message=user_message,
            assistant_message=assistant_message,
            tokens_used=tokens_used,
            cost=cost,
            metadata=metadata,
        )
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics for current session."""
        conversations = self.memory_store.get_conversation_history(
            self.current_session_id,
            limit=1000,
        )
        
        total_tokens = sum(c["tokens_used"] for c in conversations)
        total_cost = sum(c["cost"] for c in conversations)
        model_counts = {}
        
        for conv in conversations:
            model = conv["model_id"]
            model_counts[model] = model_counts.get(model, 0) + 1
        
        return {
            "session_id": self.current_session_id,
            "start_time": self.session_start.isoformat(),
            "conversation_count": len(conversations),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "model_usage": model_counts,
        }