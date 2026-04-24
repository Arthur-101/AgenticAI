#!/usr/bin/env python3
"""Main entry point for AgenticAI."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.cli.main import cli


if __name__ == "__main__":
    cli()