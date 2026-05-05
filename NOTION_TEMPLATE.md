---

## **AgenticAI Project - Multi-model AI Agent System**

- **Status:**
    - Phase 2 - UI completed (Chat page with Tauri backend integration, start/stop agent, history, summarization, smart tags)
- **Start Date:** April 19, 2025
- ****Last Updated:**** April 24, 2026

Proposed feature rollout (one‑by‑one, in priority order)

1. Tauri project scaffold – generate a new Tauri app using React + Ant Design (glass theme) as the frontend framework.
2. Python FastAPI server – set up a lightweight FastAPI process that will expose the chat endpoints (/chat, /summarize, /tags).
3. SQLite chat schema – create a messages table with columns for id, role (user/assistant), content_raw, content_summary, tags (JSON/text), created_at.
4. Summarization service – add a FastAPI route that calls the gpt‑oss‑120b model to compress a given message (≤ 400 tokens) and store the result in content_summary.
5. Tag extraction – implement optional tag generation (LLM‑based via a configurable extraction model, falling back to simple keyword heuristics) and persist tags alongside each message.
6. Context assembly endpoint – build a FastAPI route that retrieves the latest N summaries plus any summaries whose tags match the current user query, to send as the system prompt for the next model call.
7. React Chat UI component – develop the main chat panel (message list, input box, send button) with Ant Design styling, handling streaming responses from the backend.
8. Start/Stop agent controls – add UI buttons that invoke Tauri commands to spawn or terminate the FastAPI server process on demand.
9. History view & pagination – enable scrolling/back‑loading of older messages from SQLite, displaying raw or summarized content as appropriate.
10. Environment‑variable configuration – expose AGENTICAI_DEFAULT_CHAT_MODEL, AGENTICAI_SYSTEM_PROMPT, AGENTICAI_SUMMARY_MAX_TOKENS, and AGENTICAI_TAG_EXTRACTION_MODEL to both the Python server and the Tauri UI.
11. Cost & usage tracking UI – show token usage per model and accumulated cost warnings (based on the OpenRouter pricing data).
12. Automated tests – write unit tests for summarization, tag extraction, context assembly, and end‑to‑end chat flow (pytest + httpx).
13. Documentation updates – reflect the new components, env‑vars, and usage instructions in [README.md](http://readme.md/), NOTION_TEMPLATE.md, and [AGENTS.md](http://agents.md/).
14. Deferred system‑tray integration – placeholder for later addition of a Tauri system‑tray icon and hotkey support (not required for the initial UI launch).

## **Core Architecture**

- Main Controller (cheap, always running): qwen3.6-plus
- Cheap Fast Model (small tasks): gemini-2.5-flash-lite
- Planner/Reasoning Layer (complex tasks): mimo-v2-pro
- Coding/Execution Model: deepseek-v3.2
- Multimodal Layer (rare use): gemini-3.1-pro

## **Pipeline**

```python
User Input → Controller → Decision → Model/Tool → Aggregation → Output
```

## **Phase 1: Core CLI - COMPLETED ✅**

- [x]  Model routing system
- [x]  OpenRouter client
- [x]  SQLite memory store
- [x]  Basic CLI interface
- [x]  Cost tracking
- [x]  Basic tool execution

## **Phase 2: Background Service + UI - IN PROGRESS**

- [x]  Tauri system tray app (deferred)
- [x]  Windows background service
- [x]  Hotkey support
- [x]  UI Chat page (main chat, start/stop agent, history view)
- [x]  Multiple chat sessions and sidebar navigation
- [x]  Summarization & smart tags (backend compression and tag extraction)
- [x]  ChromaDB integration (Vector DB for RAG memory)
- [ ]  Advanced Document RAG (File Chunking & Vector Search)

## Phase 3: Advanced Features

- [ ]  Tool Execution Framework (MCP-style)
- [ ]  Advanced memory (Redis)
- [ ]  OCR/image processing
- [ ]  Audio/video transcription
- [ ]  Cloud synchronization

## Technical Decisions

- **Primary**: Python (LangChain ecosystem)
- **Memory**: SQLite + ChromaDB (RAG), Redis later
- **UI**: Tauri (Rust + TypeScript) for Windows tray app
- **File Processing**: .py, PDF, TXT initially

## Project Structure

```
src/
├── controller/        # Main routing logic
├── models/            # OpenRouter model wrappers
├── memory/            # SQLite + ChromaDB memory
├── tools/             # Tool definitions & execution
├── processors/        # File processing (.py, PDF, TXT)
├── aggregators/       # Multi-model output combination
└── utils/             # Shared utilities
ui/
├── src-tauri/         # Rust backend (Tauri)
└── src/               # TypeScript frontend (React/Vue)
data/
├── sqlite/            # SQLite databases
├── chroma/            # Vector embeddings
└── documents/         # Processed files
```

## Completed Files

- AGENTS.md - Project documentation and decisions
- requirements.txt - Python dependencies
- src/utils/config.py - Configuration system
- src/models/openrouter_client.py - OpenRouter API client
- src/controller/model_router.py - Model routing logic
- src/memory/sqlite_store.py - SQLite memory system
- src/controller/chat_router.py - Chat routing with context assembly
- src/memory/sqlite_store.py - SQLite memory system with chat enhancements
- src/cli/main.py - CLI interface
- src/tools/basic_tools.py - Basic tool execution
- src/api/chat_server.py - FastAPI chat server backend
- main.py - Entry point
- test_system.py - System test script
- example_usage.py - Usage examples
- README.md - Documentation
- INSTALL.md - Installation guide
- UI components:
    - ui/src/main.tsx - Main UI entry point with glass theme
    - ui/src/App.tsx - App component
    - ui/src/components/ChatPanel.tsx - Chat UI component
    - ui/src/global.css - Glass theme CSS
    - ui/src-tauri/src/lib.rs - Tauri commands for backend control

## Next Steps

1. Implement Advanced Document RAG (File Chunking & Vector Search)
2. Implement Tool Execution Framework (MCP-style)
3. Add Windows system tray integration with hotkeys
4. Implement advanced memory with Redis for multi-process sync
5. Add OCR/image processing capabilities
6. Add audio/video transcription support

## Notes

- API keys in .env (never commit)
- OpenRouter API key required
- Windows background service via Tauri
- MCP-style tool architecture

## How to Update This Page

1. **When starting a new phase**: Update the checklist
2. **When completing tasks**: Mark them as done
3. **When making technical decisions**: Add to Technical Decisions section
4. **When creating new files**: Add to Completed Files
5. **When planning next steps**: Update Next Steps section

## Cost Tracking

Keep track of:

- OpenRouter API usage costs
- Development time
- Infrastructure costs (if any)

## Testing Notes

- Run `python test_system.py` after major changes
- Test with different task types to verify model routing
- Monitor cost usage with `python main.py stats`

## Deployment Checklist

For Phase 2 deployment:

- [ ]  Build Tauri application
- [ ]  Create Windows installer
- [ ]  Set up auto-update mechanism
- [ ]  Document user installation process
- [ ]  Create user guide

## Questions & Decisions Log

| Date | Question | Decision | Reason |
| --- | --- | --- | --- |
| Apr 19, 2025 | Primary language? | Python | User preference, LangChain ecosystem |
| Apr 19, 2025 | Memory system? | SQLite + ChromaDB | Simple start, scalable |
| Apr 19, 2025 | UI framework? | Tauri | Low memory, good Windows integration |
| Apr 19, 2025 | Model routing? | Hybrid rules + ML | Balance of simplicity and intelligence |

## Links

- Project Repository: [Add your repo link]
- OpenRouter API: https://openrouter.ai/
- Tauri Documentation: https://tauri.app/
- LangChain Documentation: https://python.langchain.com/

### Terminal Commands

# cd /mnt/e/Codes/AgenticAI

# code .