# AgenticAI

Multi-model AI agent system using OpenRouter APIs with MCP-style architecture. Routes tasks to specialized models instead of relying on a single model.

## Features

- **Multi-model routing**: Intelligently routes tasks to specialized models
- **Cost optimization**: Uses cheaper models for simple tasks, expensive ones for complex tasks
- **Memory system**: SQLite stores raw conversation turns; compressed summaries (≤ 400 tokens) are stored separately; ChromaDB for RAG.
- **Summarization**: Uses free `gpt-oss-120b` to compact user and model responses.
- **Smart tags**: Automatic tag extraction enables context retrieval based on related topics.
- **Tool execution**: Managed tool execution with permission prompts
- **Cost tracking**: Monitors usage and provides warnings
- **Windows background service**: Runs as system tray app (Phase 2)
- **File processing**: Supports .py, PDF, TXT files

## Model Architecture

1. **Main Controller** (cheap, always running): qwen3.6-plus
2. **Cheap Fast Model** (small tasks): gemini-2.5-flash-lite
3. **Planner/Reasoning Layer** (complex tasks): mimo-v2-pro
4. **Coding/Execution Model**: deepseek-v3.2
5. **Multimodal Layer** (rare use): gemini-3.1-pro
- **Default chat model** configurable via env `AGENTICAI_DEFAULT_CHAT_MODEL` (defaults to `gemini-2.5-flash-lite`)
- **System prompt** configurable via env `AGENTICAI_SYSTEM_PROMPT`

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd AgenticAI
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file from `.env.example`:
```bash
cp .env.example .env
```

4. Edit `.env` and add your OpenRouter API key:
```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

## Usage

### CLI Interface

Start interactive chat:
```bash
python main.py chat
```

Send a single message:
```bash
python main.py chat -m "Hello, how are you?"
```

Force specific model:
```bash
python main.py chat -m "Write Python code to sort a list" -M deepseek
```

List available models:
```bash
python main.py models
```

Show conversation history:
```bash
python main.py history
```

Show system statistics:
```bash
python main.py stats
```

### Interactive Mode Commands

When in interactive chat mode:
- Type `exit`, `quit`, or `bye` to exit
- Type `clear` or `reset` to start new session
- Type `stats` to show session statistics

## Project Structure

```
src/
├── controller/        # Model routing logic
├── models/           # OpenRouter client wrappers
├── memory/           # SQLite + ChromaDB memory
├── tools/            # Tool definitions & execution
├── processors/       # File processing
├── aggregators/      # Multi-model output combination
└── utils/           # Shared utilities

ui/                   # Tauri UI (Phase 2)
data/                 # Database and document storage
```

## Phased Development

### Phase 1 (Current): Core CLI
- [x] Model routing system
- [x] OpenRouter client
- [x] SQLite memory store
- [x] Basic CLI interface
- [x] Cost tracking

### Phase 2: Background Service + UI
- [ ] Tauri system tray app (deferred)
- [ ] Windows background service
- [ ] Hotkey support
- [ ] UI Chat page (start/stop agent, history view, summarization, smart tags)
- [ ] File processing (.py, PDF, TXT) (pending)
- [ ] File processing (.py, PDF, TXT)
- [ ] ChromaDB integration

### Phase 3: Advanced Features
- [ ] Tool execution framework
- [ ] Advanced memory (Redis)
- [ ] OCR/image processing
- [ ] Audio/video transcription
- [ ] Cloud synchronization

## Configuration

Edit `.env` file to configure:

- **Default chat model** (`AGENTICAI_DEFAULT_CHAT_MODEL`): choose the model used for UI chat (defaults to `gemini-2.5-flash-lite`).
- **System prompt** (`AGENTICAI_SYSTEM_PROMPT`): global persona prompt applied to every response.
- **Summary max tokens** (`AGENTICAI_SUMMARY_MAX_TOKENS`): limit for compressed summaries (default 400).
- **Tag extraction model** (`AGENTICAI_TAG_EXTRACTION_MODEL`): optional model for automatic tag generation.
- **Cost limits**: Set budget warnings and limits.
- **Security**: Configure file access permissions.
- **Performance**: Adjust token limits and timeouts.

## Cost Management

The system tracks token usage and costs per model. Warnings are shown when:
- Approaching configured budget threshold
- Exceeding monthly cost limit
- Using expensive models for simple tasks

## Security

- File system access requires permission prompts
- Tool execution is sandboxed
- API keys stored in `.env` (never committed)
- Configurable file type restrictions

## Development

Run tests:
```bash
pytest tests/
```

Lint code:
```bash
ruff check src/
```

Type checking:
```bash
mypy src/
```
