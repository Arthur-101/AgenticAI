# AGENTS.md - AgenticAI

### Important:
- Do not remove this "Important:" section.
- Update this AGENTS.md file with new info everytime we decide on something or update something.
- Always keep this file updated so that the future AIs can understand how much work is done and what else to do.
- Always update the notion page for the planning and executed tasks too.
- And also update the Notion page if required.

# AI Agent System - OpenRouter + MCP Architecture

## Project Overview
Multi-model AI agent system using OpenRouter APIs with MCP-style architecture. Routes tasks to specialized models instead of single model.

## Goal
Create a multi-model AI agent system using OpenRouter APIs with MCP-style architecture that routes tasks to specialized models instead of relying on a single model. The system should support text queries, file inputs, multimodal reasoning, memory (RAG), and tool execution. The AI should run continuously in Windows background with system tray UI and shared memory across all models.

## Instructions
- Use phased approach: Phase 1 (CLI), Phase 2 (Background service + UI), Phase 3 (Advanced features)
- Language: Python (user preference), no Python avoidance
- Memory: Start with SQLite + ChromaDB, add Redis later
- File processing: Start with .py, PDF, TXT files, add images with OCR later
- Security: Managed access with permission prompts for read/write operations
- Cost management: Track usage and show warnings
- Model routing: Hybrid approach (rules + ML optimization)
- Primary use case: Personal assistant
- Priority: Low memory usage for now, advanced features for later
- User comfortable with Python, no Windows development experience

### Relevant files / directories
#### Created files:
- /mnt/e/Codes/AgenticAI/AGENTS.md - Project documentation and architecture decisions
- /mnt/e/Codes/AgenticAI/requirements.txt - Python dependencies
- /mnt/e/Codes/AgenticAI/.env.example - Environment variable template
- /mnt/e/Codes/AgenticAI/main.py - Main entry point
- /mnt/e/Codes/AgenticAI/setup.py - Python package setup
- /mnt/e/Codes/AgenticAI/test_system.py - System test script
- /mnt/e/Codes/AgenticAI/example_usage.py - Usage examples
- /mnt/e/Codes/AgenticAI/README.md - Project documentation
- /mnt/e/Codes/AgenticAI/INSTALL.md - Installation guide
- /mnt/e/Codes/AgenticAI/NOTION_TEMPLATE.md - Notion tracking template
#### Created source code directories:
- /mnt/e/Codes/AgenticAI/src/utils/config.py - Configuration management
- /mnt/e/Codes/AgenticAI/src/models/openrouter_client.py - OpenRouter API client
- /mnt/e/Codes/AgenticAI/src/controller/model_router.py - Model routing logic
- /mnt/e/Codes/AgenticAI/src/controller/chat_router.py - Chat routing with context assembly
- /mnt/e/Codes/AgenticAI/src/memory/sqlite_store.py - SQLite memory system with chat enhancements
- /mnt/e/Codes/AgenticAI/src/cli/main.py - CLI interface
- /mnt/e/Codes/AgenticAI/src/tools/basic_tools.py - Basic tool execution
- /mnt/e/Codes/AgenticAI/src/api/chat_server.py - FastAPI chat server backend
#### UI files (Phase 2):
- /mnt/e/Codes/AgenticAI/ui/package.json - UI dependencies
- /mnt/e/Codes/AgenticAI/ui/src/main.tsx - Main UI entry point with glass theme
- /mnt/e/Codes/AgenticAI/ui/src/App.tsx - App component
- /mnt/e/Codes/AgenticAI/ui/src/components/ChatPanel.tsx - Chat UI component
- /mnt/e/Codes/AgenticAI/ui/src/global.css - Glass theme CSS
- /mnt/e/Codes/AgenticAI/ui/src-tauri/Cargo.toml - Rust backend dependencies
- /mnt/e/Codes/AgenticAI/ui/src-tauri/src/lib.rs - Tauri commands for backend control
#### Directory structure created:
- /mnt/e/Codes/AgenticAI/src/ - Main source code
- /mnt/e/Codes/AgenticAI/src/controller/ - Routing logic
- /mnt/e/Codes/AgenticAI/src/models/ - Model wrappers
- /mnt/e/Codes/AgenticAI/src/memory/ - Memory systems
- /mnt/e/Codes/AgenticAI/src/tools/ - Tool definitions
- /mnt/e/Codes/AgenticAI/src/api/ - API server
- /mnt/e/Codes/AgenticAI/src/processors/ - (Empty - for Phase 2)
- /mnt/e/Codes/AgenticAI/src/aggregators/ - (Empty - for later)
- /mnt/e/Codes/AgenticAI/src/utils/ - Shared utilities
- /mnt/e/Codes/AgenticAI/ui/ - Tauri UI (Phase 2)
- /mnt/e/Codes/AgenticAI/data/ - Database and document storage

## Core Architecture

### Model Selection Strategy
1. **Main Controller** (cheap, always running): qwen3.6-plus
2. **Cheap Fast Model** (small tasks): gemini-2.5-flash-lite
3. **Planner/Reasoning Layer** (complex tasks): mimo-v2-pro
4. **Coding/Execution Model**: deepseek-v3.2
5. **Multimodal Layer** (rare use): gemini-3.1-pro

**Environment Configuration**
- `AGENTICAI_DEFAULT_CHAT_MODEL` – default chat model (default: `gemini-2.5-flash-lite`).
- `AGENTICAI_SYSTEM_PROMPT` – global system prompt to enforce a consistent persona.
- `AGENTICAI_SUMMARY_MAX_TOKENS` – max tokens for compressed summaries (default: 400).
- `AGENTICAI_TAG_EXTRACTION_MODEL` – model used for tag extraction (optional).

### Chat Enhancements
- **Persistent chat history**: SQLite stores raw user and assistant turns.
- **Compressed summaries**: After each turn, the free `gpt-oss-120b` model compacts the content to ≤ 400 tokens for efficient context.
- **Smart tags**: Automatic tag extraction (via optional LLM or heuristic) enables retrieval of related past turns when a new prompt mentions similar topics.
- **Default chat model**: Configurable via env `AGENTICAI_DEFAULT_CHAT_MODEL` (defaults to `gemini-2.5-flash-lite`).
- **System prompt**: Configurable via env `AGENTICAI_SYSTEM_PROMPT` to keep a consistent persona across all responses.

### Pipeline
```
User Input → Controller → Decision → Model/Tool → Aggregation → Output
```

## Technical Decisions

### 1. Stack Choice
- **Primary**: Python (LangChain ecosystem)
- **Memory**: SQLite + ChromaDB (RAG), Redis later
- **UI**: Tauri (Rust + TypeScript) for Windows tray app
- **File Processing**: .py, PDF, TXT initially

### 2. Phase Approach
**Phase 1**: Core CLI with model switching + basic memory
**Phase 2**: Background service + system tray UI + Document RAG
**Phase 3**: Tool Execution (MCP-style) + Advanced features (OCR, audio/video processing)

### 3. Memory Architecture
- **Short-term**: In-memory conversation context
- **Medium-term**: SQLite (conversation history, tool logs)
- **Long-term**: ChromaDB (vector embeddings for RAG)
- **Future**: Redis for multi-process sync

### 4. Security Model
- Managed file system access with permission prompts
- Tool execution with user confirmation
- Read/write/update permissions configurable

### 5. Cost Management
- Track token usage per model
- Budget warnings at thresholds
- Performance/cost optimization

### 6. Model Routing Logic
- Hybrid approach: Rules + ML optimization
- Task type detection → model selection
- Cost/performance/latency tradeoffs

## Commands

- Install: `pip install -r requirements.txt`
- Dev: `python main.py` (CLI mode)
- Build: Tauri build for Windows
- Test: `pytest tests/`
- Lint: `ruff check src/`

## Testing

- Single test: `pytest tests/test_module.py`
- Watch mode: `pytest --watch`

## Project Structure

```
src/
├── controller/        # Main routing logic
├── models/           # OpenRouter model wrappers
├── memory/           # SQLite + ChromaDB memory
├── tools/            # Tool definitions & execution
├── processors/       # File processing (.py, PDF, TXT)
├── aggregators/      # Multi-model output combination
└── utils/           # Shared utilities

ui/
├── src-tauri/        # Rust backend (Tauri)
└── src/             # TypeScript frontend (React/Vue)

data/
├── sqlite/          # SQLite databases
├── chroma/          # Vector embeddings
└── documents/       # Processed files
```

## Notes

- API keys in `.env` (never commit)
- OpenRouter API key required
- Windows background service via Tauri
- MCP-style tool architecture