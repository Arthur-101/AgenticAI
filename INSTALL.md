# Installation Guide

## Quick Start

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd AgenticAI

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure OpenRouter API
```bash
# Copy example environment file
cp .env.example .env

# Edit .env file and add your OpenRouter API key
# Get your API key from: https://openrouter.ai/keys
```

### 3. Test Installation
```bash
# Run system tests
python test_system.py

# Run examples
python example_usage.py
```

## Detailed Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- OpenRouter API key (free account available)

### Step-by-Step Setup

#### 1. Python Environment
```bash
# Check Python version
python --version  # Should be 3.8+

# Install virtual environment tool (if not installed)
pip install virtualenv

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux/Mac:
source venv/bin/activate
```

#### 2. Install Dependencies
```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or install manually
pip install openai langchain langchain-openai requests httpx sqlite3 chromadb sentence-transformers pydantic click rich python-dotenv
```

#### 3. Get OpenRouter API Key
1. Go to [OpenRouter.ai](https://openrouter.ai/)
2. Sign up for a free account
3. Navigate to [API Keys](https://openrouter.ai/keys)
4. Create a new API key
5. Copy the key

#### 4. Configure Environment
Edit the `.env` file:
```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=your_actual_api_key_here

# Optional: Customize model selection
# MODEL_QWEN=qwen/qwen-2.5-32b-instruct
# MODEL_GEMINI_FLASH=google/gemini-2.5-flash-lite
# MODEL_MIMO=mimo/mimo-v2-pro
# MODEL_DEEPSEEK=deepseek/deepseek-v3.2
# MODEL_GEMINI_PRO=google/gemini-3.1-pro

# Optional: Adjust cost limits
# COST_WARNING_THRESHOLD=10.0
# COST_LIMIT=50.0
```

#### 5. Verify Installation
```bash
# Test basic functionality
python -c "from src.utils.config import config; print('Configuration loaded successfully')"

# Test OpenRouter connection (requires API key)
python test_system.py
```

## Windows-Specific Setup

### 1. Install Python on Windows
1. Download Python from [python.org](https://python.org)
2. Run installer, check "Add Python to PATH"
3. Open Command Prompt as Administrator

### 2. Setup for Background Service (Phase 2)
```powershell
# Install Redis for Windows (optional, for Phase 2)
# Download from: https://github.com/microsoftarchive/redis/releases

# Install as Windows Service (optional)
python -m pip install pywin32
```

### 3. Create Desktop Shortcut (Optional)
Create a batch file `start_agenticai.bat`:
```batch
@echo off
cd /d "C:\path\to\AgenticAI"
call venv\Scripts\activate
python main.py chat
pause
```

## Linux/Mac Setup

### 1. Additional Dependencies
```bash
# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3-venv python3-pip

# Mac
brew install python3
```

### 2. System Service (Optional)
```bash
# Create systemd service (Linux)
sudo nano /etc/systemd/system/agenticai.service
```

Add to service file:
```ini
[Unit]
Description=AgenticAI Service
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/AgenticAI
ExecStart=/path/to/AgenticAI/venv/bin/python main.py chat
Restart=always

[Install]
WantedBy=multi-user.target
```

## Docker Installation (Optional)

### 1. Create Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py", "chat"]
```

### 2. Build and Run
```bash
docker build -t agenticai .
docker run -it --env-file .env agenticai
```

## Troubleshooting

### Common Issues

#### 1. "Module not found" errors
```bash
# Reinstall requirements
pip install -r requirements.txt --force-reinstall

# Check Python path
python -c "import sys; print(sys.path)"
```

#### 2. OpenRouter API errors
- Verify API key in `.env` file
- Check internet connection
- Visit [OpenRouter status](https://status.openrouter.ai/)

#### 3. SQLite database errors
```bash
# Check file permissions
ls -la data/sqlite/

# Remove corrupted database (backup first)
rm data/sqlite/memory.db
```

#### 4. Memory/Performance issues
```bash
# Reduce token limits in .env
MAX_TOKENS_PER_REQUEST=2000

# Use cheaper models
MODEL_GEMINI_FLASH=google/gemini-2.5-flash-lite
```

### Getting Help
1. Check the [README.md](README.md) for usage instructions
2. Run tests: `python test_system.py`
3. Check logs in `data/logs/` directory
4. Open an issue on GitHub

## Next Steps

### After Installation
1. Run the example: `python example_usage.py`
2. Try interactive chat: `python main.py chat`
3. Explore available models: `python main.py models`
4. Check costs: `python main.py stats`

### Phase 2 Setup (Background Service)
```bash
# Install Tauri prerequisites
# Follow: https://tauri.app/v1/guides/getting-started/prerequisites

# Build UI (when available)
cd ui
npm install
npm run tauri build
```

## Uninstallation

### Remove Virtual Environment
```bash
# Deactivate environment
deactivate

# Remove virtual environment
rm -rf venv
```

### Remove Data
```bash
# Remove database and documents
rm -rf data/

# Remove configuration
rm .env
```

### Full Uninstall
```bash
# Remove everything
rm -rf AgenticAI/
```