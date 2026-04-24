# Notion Page Template for AgenticAI Project

Copy this template into your Notion page to track the project.

## AgenticAI Project - Multi-model AI Agent System

**Status:** Phase 2 - UI in progress (Chat page, start/stop agent, history, summarization, smart tags)
**Start Date:** April 19, 2025

## Core Architecture

- Main Controller (cheap, always running): qwen3.6-plus
- Cheap Fast Model (small tasks): gemini-2.5-flash-lite
- Planner/Reasoning Layer (complex tasks): mimo-v2-pro
- Coding/Execution Model: deepseek-v3.2
- Multimodal Layer (rare use): gemini-3.1-pro

## Pipeline
```
User Input → Controller → Decision → Model/Tool → Aggregation → Output
```

## Phase 1: Core CLI - COMPLETED ✅

- [x] Model routing system
- [x] OpenRouter client
- [x] SQLite memory store
- [x] Basic CLI interface
- [x] Cost tracking
- [x] Basic tool execution

## Phase 2: Background Service + UI - IN PROGRESS

- [ ] Tauri system tray app (deferred)
- [ ] Windows background service
- [ ] Hotkey support
- [ ] UI Chat page (main chat, start/stop agent, history view)
- [ ] Summarization & smart tags (backend compression and tag extraction)
- [ ] File processing (.py, PDF, TXT) (pending)
- [ ] ChromaDB integration

## Phase 3: Advanced Features

- [ ] Tool execution framework
- [ ] Advanced memory (Redis)
- [ ] OCR/image processing
- [ ] Audio/video transcription
- [ ] Cloud synchronization

## Technical Decisions

- **Primary**: Python (LangChain ecosystem)
- **Memory**: SQLite + ChromaDB (RAG), Redis later
- **UI**: Tauri (Rust + TypeScript) for Windows tray app
- **File Processing**: .py, PDF, TXT initially

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

## Completed Files

- AGENTS.md - Project documentation and decisions
- requirements.txt - Python dependencies
- src/utils/config.py - Configuration system
- src/models/openrouter_client.py - OpenRouter API client
- src/controller/model_router.py - Model routing logic
- src/memory/sqlite_store.py - SQLite memory system
- src/cli/main.py - CLI interface
- src/tools/basic_tools.py - Basic tool execution
- main.py - Entry point
- test_system.py - System test script
- example_usage.py - Usage examples
- README.md - Documentation
- INSTALL.md - Installation guide
- UI components (Chat page, start/stop agent, history, summarization, smart tags) – in progress

## Next Steps

1. Test with actual OpenRouter API key
2. Add file processors (.py, PDF, TXT)
3. Implement ChromaDB for RAG
4. Complete UI Chat page (start/stop agent, history, summarization, smart tags) – remaining: tray, hotkeys, file processing, ChromaDB
5. Add Windows service integration

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
- [ ] Build Tauri application
- [ ] Create Windows installer
- [ ] Set up auto-update mechanism
- [ ] Document user installation process
- [ ] Create user guide

## Questions & Decisions Log

| Date | Question | Decision | Reason |
|------|----------|----------|--------|
| Apr 19, 2025 | Primary language? | Python | User preference, LangChain ecosystem |
| Apr 19, 2025 | Memory system? | SQLite + ChromaDB | Simple start, scalable |
| Apr 19, 2025 | UI framework? | Tauri | Low memory, good Windows integration |
| Apr 19, 2025 | Model routing? | Hybrid rules + ML | Balance of simplicity and intelligence |

## Links

- Project Repository: [Add your repo link]
- OpenRouter API: https://openrouter.ai/
- Tauri Documentation: https://tauri.app/
- LangChain Documentation: https://python.langchain.com/