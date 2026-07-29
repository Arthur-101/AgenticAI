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
1. **Main Controller** (cheap, always running): qwen3.5-flash-02-23
2. **Cheap Fast Model** (small tasks): gemini-2.5-flash-lite
3. **Planner/Reasoning Layer** (complex tasks): deepseek-v4-pro / mimo-v2.5-pro
4. **Coding/Execution Model**: deepseek-v4-flash
5. **Multimodal Layer** (rare use): gemini-2.5-flash-lite

**Environment Configuration**
- `AGENTICAI_DEFAULT_CHAT_MODEL` – default chat model (default: `qwen3.5-flash-02-23`).
- `AGENTICAI_SYSTEM_PROMPT` – global system prompt to enforce a consistent persona.
- `AGENTICAI_SUMMARY_MAX_TOKENS` – max tokens for compressed summaries (default: 400).
- `AGENTICAI_TAG_EXTRACTION_MODEL` – model used for tag extraction (optional).

### Chat Enhancements
- **Persistent chat history**: SQLite stores raw user and assistant turns.
- **Compressed summaries**: After each turn, the free `gpt-oss-120b` model compacts the content to ≤ 400 tokens for efficient context.
- **Smart tags**: Automatic tag extraction (via optional LLM or heuristic) enables retrieval of related past turns when a new prompt mentions similar topics.
- **Default chat model**: Configurable via env `AGENTICAI_DEFAULT_CHAT_MODEL` (defaults to `qwen3.5-flash-02-23`).
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
**Phase 3**: Tool Execution (MCP-style), Intelligent Routing, Advanced Redis Memory [COMPLETED] + Stateful Shared Terminal, System Tray polish, Gemini Audio/Video processing [IN PROGRESS]

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

- API keys in `.env` (never commit)
- OpenRouter API key required
- Windows background service via Tauri
- MCP-style tool architecture

### Windows Native Migration, Terminal Fixes & Document RAG:
- **Terminal Manager (`src/tools/terminal_manager.py`)**: Migrated to `pywinpty` on Windows. Fixed PTY read signature (`read(blocking=False)`). Implemented `clean_ansi()` logic with PSReadLine cursor-positioning code splitting (`\x1b[row;colH`) and prompt-grouping line filters to eliminate all intermediate typing typos (`ccdcd`, `llsls`).
- **Web Search (`src/tools/basic_tools.py`)**: Updated dependencies to use `ddgs>=9.0.0` with fallback for `duckduckgo-search`.
- **Tauri Python Resolver (`ui/src-tauri/src/lib.rs`)**: Added dynamic ancestor traversal to locate project root and `.venv/Scripts/python.exe` reliably regardless of working directory.
- **Document RAG & Multi-Format Processor (`src/processors/file_processor.py`)**: Added support for `.py`, `.pdf`, `.txt`, `.md`, `.json`, `.csv`, `.js`, `.ts`, `.tsx`, `.html`, `.css`, `.rs`, `.log`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.mp3`, `.mp4`, `.wav`, etc. Embedded base64 `data_url` generation for image files to bypass webview asset protocol origin restrictions. Integrated ChromaDB document chunk retrieval (`search_documents`) into `ChatRouter._assemble_context`.
- **Gemini / ChatGPT Style Attachment UI (`ui/src/components/ChatPanel.tsx`)**:
  - Rendered square rounded thumbnail cards (`68x68px`) with hover scale, zoom overlays, and close buttons for attached images in the draft input container.
  - Rendered attached thumbnail cards above user chat bubbles in message history.
  - Built full-screen **Image Lightbox Zoom Modal** for high-resolution image inspection.
  - Implemented auto-healing `onError` handler on `<img />` tags to dynamically fetch Base64 Data URLs from Python if asset protocol loading fails.
  - Updated `sendMessage` payload to automatically append file tags (`[Attached File: ...| Path: ...]`) to guarantee 100% RAG retrieval even for non-semantic prompts.
- **Windows System Tray & Background Service (`ui/src-tauri/src/lib.rs` & `ui/src/components/ChatPanel.tsx`)**:
  - Intercepted `CloseRequested` window event to minimize the app to the Windows System Tray on close instead of exiting.
  - Built native System Tray Context Menu (`🟢 AgenticAI (Engine Active)`, `🖥️ Show Studio Window`, `➕ Start New Chat`, `⚡ Toggle AI Engine`, `❌ Quit AgenticAI`).
  - Added left-click toggle on the System Tray icon to instantly hide/unhide and focus the app window.
  - Connected `trigger-new-chat` and `trigger-toggle-engine` IPC event triggers from Tauri to React.
- **MCP Configuration & Notion Master Project Tracker**:
  - Configured Notion MCP server integration globally in settings.
  - Successfully connected to Notion workspace via MCP tools (`call_mcp_tool`).
  - Created and updated standalone top-level Notion page: `🚀 AgenticAI - Master Project Tracker & Executed Status` (Page ID: `341c8b7b-66a5-80ed-b7ba-dddb5d3ea0d9`).
  - Populated Notion page with project overview, model routing architecture, completed Phase 1/2/3 milestones, active tasks, and future roadmap.
- **Advanced Redis Memory Synchronization & Auto-Start (`src/memory/redis_store.py`)**:
  - Bundled portable Redis v5.0 binary at `bin/redis/redis-server.exe` — zero install required.
  - Auto-starts bundled Redis on app launch, stores data in `data/redis/dump.rdb`.
  - Registers `atexit` hook to cleanly terminate Redis when the app quits.
  - Uses `protocol=2` (RESP2) for redis-py v5+ compatibility with bundled Redis v5.0.
  - Implemented retry loop (10x × 0.5s) to wait for Redis to fully bind port 6379 before connecting.
  - Implemented multi-process Pub/Sub message broadcasting (`publish_message`, `subscribe_events`).
  - Implemented active session state and assembled context caching (`cache_assembled_context`, `get_assembled_context`).
  - Implemented distributed locking (`acquire_lock`, `release_lock`) for multi-process concurrency control.
  - Added auto-reconnection and graceful SQLite fallback when Redis is offline.
- **Global Memory & Persona System UI (`ui/src/components/ChatPanel.tsx` & `src/api/embedded_backend.py`)**:
  - Fixed memory loading invoke call (`get_all_memories`).
  - Fixed Tauri IPC parameter names (`messageId`, `memoryId`) for `update_memory` and `delete_memory` so editing and deleting entries work cleanly.
  - Added automatic memory fetching whenever the Settings modal opens.
  - Built **Add New Global Memory** form allowing manual entry creation.
  - Implemented `add_memory` endpoint across JSON-RPC backend (`embedded_backend.py`), Tauri IPC (`lib.rs`), SQLite (`sqlite_store.py`), and ChromaDB vector store.
  - Full support for viewing, adding, editing, deleting, and auto-extracting conversational facts globally.
- **Smart Memory Curation & Auto-Consolidation (`src/models/openrouter_client.py` & `src/controller/chat_router.py`)**:
  - Refined memory extraction system prompt to strictly filter out transient commentary ("they fixed it", "duration was 5 mins", "ran a terminal command") and extract ONLY enduring personal facts, user preferences, and system specs.
  - Built `consolidate_memory_actions` engine: Compares new facts against existing memories to automatically `UPDATE`, `ADD`, or `SKIP` entries in both SQLite and ChromaDB vector database.
- **Dark Glass Modal & App-Wide Theme System (`ui/src/main.tsx`, `ui/src/global.css`, `ui/src/components/ChatPanel.tsx`)**:
  - Configured `ConfigProvider` with `algorithm: theme.darkAlgorithm` globally in `main.tsx` so all Ant Design components (Modals, Cards, Popconfirms, Inputs, Tooltips, Lists) default to dark mode.
  - Applied dark glassmorphic CSS overrides (`rgba(15, 23, 42, 0.95)`, `20px` backdrop blur, cyan focus outlines, dark input controls) matching the overall app design.
- **Multi-Model Sub-Agent Collaboration & Output Aggregator (`src/aggregators/sub_agent_manager.py` & `src/aggregators/consensus_aggregator.py`)**:
  - Built `SubAgentManager`: Spawns parallel background workers (`deepseek/deepseek-v4-flash` for coding, `deepseek/deepseek-v4-pro` for reasoning/architecture, and `google/gemini-2.5-flash-lite` for multimodal attachments) using `asyncio.gather()`.
  - Built `ConsensusAggregator`: Synthesizes sub-agent outputs via `google/gemini-2.5-flash-lite` or `qwen/qwen3.5-flash-02-23` to eliminate duplicates, resolve conflicting suggestions, and output a unified master response.
  - Added **🤝 Multi-Model Team** option to the model selection dropdown in `ui/src/components/ChatPanel.tsx`.
- **Model & API Configuration Manager (`src/models/provider_router.py`, `src/memory/sqlite_store.py`, `src/memory/redis_store.py`, `ui/src/components/ChatPanel.tsx`)**:
  - Built `ProviderRouter`: Direct HTTP / SDK dispatching for OpenRouter, OpenAI, Google AI Studio, and Anthropic APIs.
  - Multi-provider API Key storage in SQLite `api_keys` table with `.env` fallback. Added `test_api_key` verification endpoint.
  - Dynamic Role Model Swapping: Update model assignment for any role (Orchestrator, Coding, Reasoning, Multimodal, Synthesizer) directly in Settings. Hot-reloaded into Redis (`set_role_model` / `get_role_model`) and takes effect from the very next prompt mid-session!
  - Added **Key & Model Settings** tab to Settings modal with role assignment cards, API key form, and live key testing.
  - Fixed `SQLiteMemoryStore` class method scope so `save_role_assignment`, `get_role_assignments`, `save_api_key`, `get_api_keys`, `get_api_key_by_provider`, and `delete_api_key` are properly located on `SQLiteMemoryStore` instead of `SessionManager`.
  - Updated Google AI Studio test model target from deprecated `gemini-2.5-flash` to active `gemini-2.5-flash-lite` to resolve HTTP 404 test failures.

## Planned Future Roadmap Tasks (Notion Tracked)
- **Task 1: Live Token Usage & Budget Warning Tracker Widget**: Add live token/cost meter in top header bar showing expenditure ($) per session/model with dynamic OpenRouter pricing catalog sync, multi-tier protection (75% Soft Alert, 90% Auto-Downgrade, 100% Hard Cap), sub-agent cost attribution tagging, atomic Redis sync, and an analytics drawer with spending graphs.
- **Task 2: Expanded Native MCP Tools**: Build `SystemMonitorTool` (CPU/RAM/Disk), `ProcessManagerTool` (active task management), and `GitInspectorTool` (git diffs/commits).
- **Task 3: Autonomous Scheduled Background Workflows & Reminders**: One-shot & cron background scheduler for periodic health checks, repo backups, and AI reminders.
- **Task 4: Voice Input & Speech-to-Text Dictation**: Mic button in input bar for hands-free prompt dictation.