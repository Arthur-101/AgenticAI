from src.tools.basic_tools import ToolManager
from typing import Dict, Any

def patch_ask_expert(tm: ToolManager, original_func):
    def new_func(model_name: str, prompt: str, file_paths: list = None) -> Dict[str, Any]:
        return original_func(model_name, prompt, file_paths)
    return new_func
