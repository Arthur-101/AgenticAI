import os
import chromadb
from typing import List, Dict, Any, Optional
import uuid
import logging

logger = logging.getLogger(__name__)

class VectorMemoryStore:
    def __init__(self, persist_directory: str = "data/chroma"):
        """Initialize ChromaDB client and collections."""
        os.makedirs(persist_directory, exist_ok=True)
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Create or get collections
        # We use default embedding function (all-MiniLM-L6-v2) under the hood
        # if no specific embedding function is provided. It automatically downloads
        # sentence-transformers model.
        try:
            self.chat_collection = self.client.get_or_create_collection(
                name="chat_history",
                metadata={"hnsw:space": "cosine"}
            )
            self.user_memories_collection = self.client.get_or_create_collection(
                name="user_memories",
                metadata={"hnsw:space": "cosine"}
            )
            self.document_collection = self.client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
        except Exception as e:
            logger.error(f"Failed to initialize Chroma collections: {e}")
            raise

    def add_message(self, session_id: str, role: str, content: str, message_id: Optional[str] = None):
        """Add a chat message to the vector store."""
        if not content or len(content.strip()) < 10:
            return # Skip very short messages
            
        doc_id = message_id or str(uuid.uuid4())
        
        try:
            self.chat_collection.add(
                documents=[content],
                metadatas=[{"session_id": session_id, "role": role}],
                ids=[f"msg_{doc_id}"]
            )
        except Exception as e:
            logger.error(f"Error adding message to vector store: {e}")

    def add_document(self, file_path: str, content: str, chunk_size: int = 1000, chunk_overlap: int = 200):
        """Add a document to the vector store, chunked for better retrieval."""
        if not content:
            return
            
        # Basic chunking
        chunks = []
        for i in range(0, len(content), chunk_size - chunk_overlap):
            chunk = content[i:i + chunk_size]
            chunks.append(chunk)
            
        if not chunks:
            return
            
        ids = [f"{file_path}_{i}" for i in range(len(chunks))]
        metadatas = [{"file_path": file_path, "chunk": i} for i in range(len(chunks))]
        
        try:
            self.document_collection.add(
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
        except Exception as e:
            logger.error(f"Error adding document to vector store: {e}")

    def add_user_memory(self, memory_id: str, content: str):
        """Add an extracted factual memory to the vector store."""
        if not content or len(content.strip()) < 5:
            return
            
        try:
            self.user_memories_collection.add(
                documents=[content],
                metadatas=[{"type": "fact"}],
                ids=[f"fact_{memory_id}"]
            )
        except Exception as e:
            logger.error(f"Error adding user memory to vector store: {e}")

    def update_user_memory(self, memory_id: str, content: str):
        """Update an extracted factual memory in the vector store."""
        try:
            self.user_memories_collection.update(
                documents=[content],
                ids=[f"fact_{memory_id}"]
            )
        except Exception as e:
            logger.error(f"Error updating user memory in vector store: {e}")

    def delete_user_memory(self, memory_id: str):
        """Delete an extracted factual memory from the vector store."""
        try:
            self.user_memories_collection.delete(
                ids=[f"fact_{memory_id}"]
            )
        except Exception as e:
            logger.error(f"Error deleting user memory in vector store: {e}")

    def search_user_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant factual user memories."""
        if not query or len(query.strip()) < 3:
            return []
            
        try:
            results = self.user_memories_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            formatted_results = []
            if results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "content": results["documents"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching user memories vector store: {e}")
            return []

    def search_similar_messages(self, query: str, session_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search for similar past messages."""
        if not query or len(query.strip()) < 3:
            return []
            
        try:
            where_clause = {"session_id": session_id} if session_id else None
            
            results = self.chat_collection.query(
                query_texts=[query],
                n_results=limit,
                where=where_clause
            )
            
            formatted_results = []
            if results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []

    def search_documents(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search across all indexed documents."""
        if not query or len(query.strip()) < 3:
            return []
            
        try:
            results = self.document_collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            formatted_results = []
            if results["documents"] and len(results["documents"]) > 0:
                for i in range(len(results["documents"][0])):
                    formatted_results.append({
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None
                    })
            return formatted_results
        except Exception as e:
            logger.error(f"Error searching document store: {e}")
            return []
