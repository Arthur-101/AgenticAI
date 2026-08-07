# 🚀 AgenticAI

AgenticAI is a professional-grade, multi-model AI agent system built on a modular Model Context Protocol (MCP) style architecture. Rather than relying on a single large language model for all tasks, AgenticAI dynamically orchestrates, selects, and routes tasks to specialized models optimized for speed, cost, reasoning, or multimodal capabilities. 

Featuring a modern React + Ant Design dark glassmorphic UI wrapped in a native Windows Tauri system tray application, the system incorporates real-time multi-process synchronization, a robust shared memory layer, local MCP tool hosts, and multi-agent consensus pipelines.

---

## 🔑 Core Features

- **Intelligent Heterogeneous Routing**: Automatically determines task complexity and routes sub-tasks to optimized models (Qwen, Gemini, DeepSeek, or Mimo) or lets users dynamically configure distinct models for specific workflow roles.
- **Tauri Desktop UI & Windows Tray Integration**: A sleek React-based front-end with an advanced glassmorphism theme that minimizes to the Windows System Tray, featuring left-click toggle visibility and native context menu commands.
- **Zero-Install Portable Redis Memory Sync**: Automatically spawns and manages a bundled portable Redis server on start for multi-process distributed locks, active session caching, and Pub/Sub communication with automatic SQLite fallbacks.
- **Smart Facts Curation & Consolidation**: Uses conversational history to automatically extract enduring facts, user preferences, and system specs. Synthesizes updates using a deterministic `UPDATE`, `ADD`, or `SKIP` evaluation loop, persisting memory in SQLite and indexing it in ChromaDB for high-accuracy RAG.
- **Multi-Model Team Collaboration & Consensus Aggregator**: Parallelized team reasoning using `SubAgentManager` (spawning specialized experts in coding, planning, and vision) combined with a `ConsensusAggregator` to resolve contradictions and output a unified master response.
- **Local MCP Client Host**: Thread-safe host architecture that loads `data/mcp_config.json`, manages stdio-based MCP servers (e.g., Tavily, Spotify) as background subprocesses, exposes them dynamically, and streams logs to the UI settings drawer.
- **Multi-Format Attachment Processor & Image Lightbox**: Gemini/ChatGPT-style attachment manager that processes PDFs, Code, Log files, and Images (rendering them as base64 in the UI and routing them natively via provider-level vision APIs like Gemini and OpenAI).
- **Stateful Terminal Manager**: Migrated to `pywinpty` on Windows, featuring an ANSI-escape code cleaning filter to support persistent shell interactions with the host system safely.
- **Direct Provider REST APIs**: Leverages native, zero-quota REST dispatchers for Google AI Studio, Anthropic, OpenAI, Groq, and Mistral AI, with a automatic failover fallback to OpenRouter.

---

## 📐 System Architecture

### Pipeline Flow

```
                     ┌──────────────────┐
                     │    User Input    │
                     └────────┬─────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │   Orchestrator   │
                     └────────┬─────────┘
                              │ (Decomposes & Selects)
                              ▼
             ┌────────────────┼────────────────┐
             │                │                │
             ▼                ▼                ▼
      ┌────────────┐   ┌────────────┐   ┌────────────┐
      │ Sub-Agent  │   │ Sub-Agent  │   │ Local MCP  │
      │  (Coding)  │   │(Reasoning) │   │   Tools    │
      └──────┬─────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             └────────────────┼────────────────┘
                              │ (Submits Proposals)
                              ▼
                     ┌──────────────────┐
                     │    Synthesizer   │
                     └────────┬─────────┘
                              │ (Consensus Analysis)
                              ▼
                     ┌──────────────────┐
                     │   Final Output   │
                     └──────────────────┘
```

### Dedicated Model Roles

You can map any friendly model id from OpenRouter, Google AI Studio, OpenAI, Anthropic, Groq, or Mistral AI to the following roles:

| Role | Default Model | Primary Responsibility |
| :--- | :--- | :--- |
| **Orchestrator** | `qwen/qwen3.5-flash-02-23` | Session supervisor, intent classifier, and router. |
| **Cheap Fast Model** | `google/gemini-2.5-flash-lite` | Simple chats, standard inquiries, text-only queries. |
| **Reasoning Engine** | `deepseek/deepseek-v4-pro` | Complex algorithmic design, planning, math, and workflows. |
| **Coding Specialist** | `deepseek/deepseek-v4-flash` | Code generation, debugging, refactoring, and AST scanning. |
| **Multimodal Processor** | `google/gemini-2.5-flash-lite` | Image inspection, video parsing, PDF scanning, and audio OCR. |
| **Memory / Summarizer** | `openai/gpt-oss-120b` | Fact extraction, database pruning, context summarization. |
| **Speech-to-Text (STT)**| `whisper-1` | Micro-button voice dictation to chat box. |
| **Text-to-Speech (TTS)**| `tts-1` | Speech synthesis voice response. |

---

## 📁 Repository Structure

```
AgenticAI/
├── src/
│   ├── api/             # FastAPI endpoints & WebSocket communication
│   ├── controller/      # Model routers, prompt templates & context assembly
│   ├── models/          # Direct HTTP client wrappers & OpenRouter bindings
│   ├── memory/          # SQLite stores, ChromaDB indexes, & Redis sync
│   ├── processors/      # Image base64 generators & file parsing utilities
│   ├── tools/           # Terminal manager, file explorer, & MCP hosts
│   ├── aggregators/     # Sub-agent managers & consensus combiners
│   └── utils/           # Configuration managers and cost trackers
├── ui/
│   ├── src-tauri/       # Tauri configuration & Rust window-tray IPC handles
│   └── src/             # React + Ant Design glassmorphic UI components
├── bin/
│   └── redis/           # Portable pre-compiled Redis binaries
└── data/
    ├── sqlite/          # Main SQLite storage files
    ├── chroma/          # Vector embeddings index databases
    └── documents/       # Local cached documents & media files
```

---

## ⚡ Getting Started

### Prerequisites

- **Python 3.9+**
- **Node.js v18+** & **npm**
- **Cargo / Rust** (Only required if compilation of Tauri binaries is needed)

### 1. Installation

Clone this repository and set up a virtual environment:

```bash
git clone <repository-url>
cd AgenticAI

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python backend packages
pip install -r requirements.txt
```

Navigate to the `ui` directory and install front-end dependencies:

```bash
cd ui
npm install
```

### 2. Configuration Setup

Copy the example environment template and configure your API keys:

```bash
cp .env.example .env
```

Open `.env` and fill in the target variables:
```env
# OpenRouter Configuration
OPENROUTER_API_KEY=your_key_here

# Direct API Provider keys (Optional, fallback to OpenRouter if not set)
GEMINI_API_KEY=your_google_studio_key_here
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
GROQ_API_KEY=your_groq_key_here
MISTRAL_API_KEY=your_mistral_key_here

# Local Database Configuration
SQLITE_DB_PATH=data/agenticai.db
CHROMA_DB_PATH=data/chroma
```

---

## 🖥️ Running the System

You can run AgenticAI in CLI mode, start the JSON-RPC backend directly, or launch the Tauri Desktop UI wrapper.

### CLI Mode

To interact directly from the terminal:

```bash
# Start an interactive CLI chat
python main.py chat

# Show system statistics and costs
python main.py stats

# List available models
python main.py models

# Show conversation history
python main.py history
```

### Desktop UI Mode (Tauri)

To launch the desktop interface:

```bash
cd ui
npm run tauri dev
```

This starts the Ant Design dark glassmorphic window, boots the dynamic Python backend, spins up the portable Redis database, and creates a system tray icon `🟢 AgenticAI` on Windows.

---

## 🛠️ Security and Cost Management

- **User-in-the-Loop Permissions**: Operations modifying files, writing to directories, or launching sub-agent tool runs require interactive confirmation or desktop notification consent.
- **Budget Protection**: Configurable in settings or `.env`, supporting alert thresholds (e.g., 75% warn) and hard caps (100% block/auto-downgrade) to prevent runaway charges.
- **Zero-Quota API Checks**: Model settings screen queries catalog endpoint models directly rather than executing dummy text completions, avoiding unnecessary cost or quota exceptions.
