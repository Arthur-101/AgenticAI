"""Basic tools for the AI agent."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import json
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from src.processors.file_processor import FileProcessor


class BasicTools:
    """Basic system tools for the AI agent."""
    
    def __init__(self, require_permission: bool = True):
        self.require_permission = require_permission
        self.permission_cache = {}
    
    def get_current_directory(self) -> Dict[str, Any]:
        """Get current working directory."""
        return {
            "success": True,
            "result": os.getcwd(),
            "message": "Current working directory retrieved",
        }
    
    def list_files(self, directory: Optional[str] = None) -> Dict[str, Any]:
        """List files in a directory."""
        try:
            target_dir = Path(directory) if directory else Path.cwd()
            
            if not target_dir.exists():
                return {
                    "success": False,
                    "result": None,
                    "message": f"Directory does not exist: {target_dir}",
                }
            
            if not target_dir.is_dir():
                return {
                    "success": False,
                    "result": None,
                    "message": f"Path is not a directory: {target_dir}",
                }
            
            files = []
            for item in target_dir.iterdir():
                file_info = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                }
                files.append(file_info)
            
            return {
                "success": True,
                "result": files,
                "message": f"Found {len(files)} items in {target_dir}",
            }
            
        except PermissionError:
            return {
                "success": False,
                "result": None,
                "message": f"Permission denied for directory: {directory}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error listing files: {e}",
            }
    
    def read_file(self, file_path: str, require_permission: Optional[bool] = None) -> Dict[str, Any]:
        """Read content of a file."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                return {
                    "success": False,
                    "result": None,
                    "message": f"File does not exist: {file_path}",
                }
            
            if not path.is_file():
                return {
                    "success": False,
                    "result": None,
                    "message": f"Path is not a file: {file_path}",
                }
            
            # Check permission if required
            if (require_permission or self.require_permission) and not self._has_permission("read", file_path):
                return {
                    "success": False,
                    "result": None,
                    "message": f"Permission denied for reading: {file_path}",
                }
            
            # Read file using FileProcessor
            content = FileProcessor.process_file(str(path))
            
            return {
                "success": True,
                "result": content,
                "message": f"File read successfully: {file_path}",
                "metadata": {
                    "size": len(content),
                    "lines": content.count('\n') + 1,
                }
            }
            
        except PermissionError:
            return {
                "success": False,
                "result": None,
                "message": f"Permission denied for file: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error reading file: {e}",
            }
    
    def write_file(self, file_path: str, content: str, require_permission: Optional[bool] = None) -> Dict[str, Any]:
        """Write content to a file."""
        try:
            path = Path(file_path)
            
            # Check permission if required
            if (require_permission or self.require_permission) and not self._has_permission("write", file_path):
                return {
                    "success": False,
                    "result": None,
                    "message": f"Permission denied for writing: {file_path}",
                }
            
            # Create directory if it doesn't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "result": file_path,
                "message": f"File written successfully: {file_path}",
                "metadata": {
                    "size": len(content),
                    "lines": content.count('\n') + 1,
                }
            }
            
        except PermissionError:
            return {
                "success": False,
                "result": None,
                "message": f"Permission denied for file: {file_path}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error writing file: {e}",
            }
    
    def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command."""
        try:
            # Security check: disallow dangerous commands
            dangerous_patterns = ["rm -rf", "format", "dd if=", "mkfs", ":(){:|:&};:"]
            for pattern in dangerous_patterns:
                if pattern in command.lower():
                    return {
                        "success": False,
                        "result": None,
                        "message": f"Command contains potentially dangerous pattern: {pattern}",
                    }
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            return {
                "success": result.returncode == 0,
                "result": {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
                "message": f"Command executed with return code: {result.returncode}",
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "result": None,
                "message": f"Command timed out after {timeout} seconds",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error executing command: {e}",
            }
    
    def calculate(self, expression: str) -> Dict[str, Any]:
        """Calculate a mathematical expression."""
        try:
            # Security: only allow safe operations
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in expression):
                return {
                    "success": False,
                    "result": None,
                    "message": "Expression contains invalid characters",
                }
            
            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, {})
            
            return {
                "success": True,
                "result": result,
                "message": f"Calculation successful: {expression} = {result}",
            }
            
        except ZeroDivisionError:
            return {
                "success": False,
                "result": None,
                "message": "Division by zero",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error calculating expression: {e}",
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        import platform
        
        return {
            "success": True,
            "result": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "current_directory": os.getcwd(),
            },
            "message": "System information retrieved",
        }
    
    def get_current_datetime(self) -> Dict[str, Any]:
        """Get the current date and time."""
        from datetime import datetime
        import platform
        import subprocess
        
        is_wsl = 'linux' in platform.system().lower() and 'microsoft' in platform.release().lower()
        if is_wsl:
            try:
                # Use powershell to get the exact host Windows time since WSL clocks often drift or are stuck in UTC
                result = subprocess.run(["powershell.exe", "-Command", "Get-Date -Format 'yyyy-MM-dd HH:mm:ss dddd'"], capture_output=True, text=True, timeout=2)
                if result.returncode == 0 and result.stdout.strip():
                    date_str = result.stdout.strip()
                    return {
                        "success": True,
                        "result": {
                            "datetime": date_str,
                            "note": "Time retrieved from Windows Host"
                        },
                        "message": "Current datetime retrieved",
                    }
            except Exception:
                pass
                
        now = datetime.now()
        return {
            "success": True,
            "result": {
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
            },
            "message": "Current datetime retrieved",
        }

    def web_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search the web for a query."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return {
                    "success": True,
                    "result": results,
                    "message": f"Found {len(results)} results for '{query}'",
                }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error performing web search: {e}",
            }
            
    def fetch_webpage(self, url: str) -> Dict[str, Any]:
        """Fetch and extract text from a webpage."""
        try:
            response = httpx.get(url, timeout=15.0, follow_redirects=True, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()
            
            text = soup.get_text(separator="\n", strip=True)
            # Truncate if too long (e.g., 20000 chars roughly 5000 tokens)
            if len(text) > 20000:
                text = text[:20000] + "\n...[truncated]"
                
            return {
                "success": True,
                "result": text,
                "message": f"Webpage fetched and parsed: {url}",
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error fetching webpage: {e}",
            }
    
    def ask_expert_model(self, model_name: str, prompt: str, file_paths: Optional[list] = None) -> Dict[str, Any]:
        """Ask an expert AI model a specific question or delegate a task."""
        try:
            from src.utils.config import config
            import httpx
            import json
            import base64
            
            # Map friendly names to actual model IDs
            mapping = {
                "qwen": config.settings.model_qwen,
                "gemini": config.settings.model_gemini_flash,
                "gemini_pro": config.settings.model_gemini_pro,
                "deepseek": config.settings.model_deepseek,
                "mimo": config.settings.model_mimo,
            }
            
            actual_model = mapping.get(model_name.lower(), model_name)
            
            # Prepare context from files if provided
            content_list = [{"type": "text", "text": prompt}]
            
            if file_paths:
                import mimetypes
                for path_str in file_paths:
                    try:
                        p = Path(path_str)
                        if p.exists() and p.is_file():
                            mime_type, _ = mimetypes.guess_type(str(p))
                            
                            if mime_type and mime_type.startswith('image/'):
                                # Handle image
                                with open(p, "rb") as image_file:
                                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                                    content_list.append({
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{encoded_string}"
                                        }
                                    })
                            elif p.stat().st_size < 1024 * 1024:  # 1MB limit for text
                                # Handle text
                                content = FileProcessor.process_file(str(p))
                                content_list[0]["text"] += f"\n\n--- Contents of {p.name} ---\n{content}\n"
                    except Exception as e:
                        content_list[0]["text"] += f"\n\n(Error reading {path_str}: {str(e)})\n"
            
            messages = [
                {"role": "system", "content": "You are an expert sub-agent called by the primary orchestrator. Provide direct, concise answers with zero conversational filler. Your output will be parsed directly by another AI."},
                {"role": "user", "content": content_list if len(content_list) > 1 else content_list[0]["text"]}
            ]
            
            request_data = {
                "model": actual_model,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": 4000
            }
            
            print(f"🤖 Supervisor delegating task to {actual_model}...")
            
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{config.settings.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_data
                )
                response.raise_for_status()
                data = response.json()
                
                # Track cost
                if "usage" in data:
                    usage = data["usage"]
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    config.track_cost(actual_model, input_tokens, output_tokens)
                
                if "choices" in data and data["choices"]:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    return {
                        "success": True,
                        "result": content,
                        "message": f"Expert {model_name} responded successfully"
                    }
                    
            return {
                "success": False,
                "result": None,
                "message": "No response generated by expert model"
            }
            
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error asking expert model: {str(e)}"
            }

    def _has_permission(self, action: str, resource: str) -> bool:
        """Check if permission is granted for an action on a resource."""
        permission_key = f"{action}:{resource}"
        
        if permission_key in self.permission_cache:
            return self.permission_cache[permission_key]
        
        # In a real implementation, this would show a user prompt
        # For now, we'll simulate based on file type
        from src.utils.config import config
        
        path = Path(resource)
        if path.suffix.lower() in [".py", ".txt", ".md", ".json"]:
            # Allow read/write for text files
            self.permission_cache[permission_key] = True
            return True
        elif path.suffix.lower() in [".exe", ".dll", ".sys"]:
            # Deny for system files
            self.permission_cache[permission_key] = False
            return False
        else:
            # Ask user (simulated)
            print(f"⚠️  Permission requested: {action} on {resource}")
            print("   Type 'allow' to grant or 'deny' to reject")
            # Simulate user allowing
            self.permission_cache[permission_key] = True
            return True
    
    def get_available_tools(self) -> Dict[str, Any]:
        """Get list of available tools with descriptions."""
        tools = {
            "get_current_directory": {
                "description": "Get current working directory",
                "parameters": {},
                "returns": "Current directory path",
            },
            "list_files": {
                "description": "List files in a directory",
                "parameters": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path (optional, defaults to current)",
                        "required": False,
                    }
                },
                "returns": "List of files and directories",
            },
            "read_file": {
                "description": "Read content of a file",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to read",
                        "required": True,
                    }
                },
                "returns": "File content",
            },
            "write_file": {
                "description": "Write content to a file",
                "parameters": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to write",
                        "required": True,
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                        "required": True,
                    }
                },
                "returns": "Path to written file",
            },
            "execute_command": {
                "description": "Execute a shell command",
                "parameters": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                        "required": True,
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30)",
                        "required": False,
                    }
                },
                "returns": "Command output",
            },
            "calculate": {
                "description": "Calculate a mathematical expression",
                "parameters": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression",
                        "required": True,
                    }
                },
                "returns": "Calculation result",
            },
            "get_system_info": {
                "description": "Get system information",
                "parameters": {},
                "returns": "System information dictionary",
            },
            "web_search": {
                "description": "Search the web for a query to find recent or relevant information",
                "parameters": {
                    "query": {
                        "type": "string",
                        "description": "Search query string",
                        "required": True,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 5)",
                        "required": False,
                    }
                },
                "returns": "List of search result dictionaries with title, href, and body",
            },
            "fetch_webpage": {
                "description": "Fetch and extract text content from a webpage URL",
                "parameters": {
                    "url": {
                        "type": "string",
                        "description": "URL of the webpage to fetch",
                        "required": True,
                    }
                },
                "returns": "Extracted text content of the webpage",
            },
            "ask_expert_model": {
                "description": "Delegate a specialized task to an expert AI model (e.g., 'deepseek' for coding, 'gemini' for multimodal/vision, 'mimo' for complex reasoning). Use this when you cannot fulfill a request with your current capabilities.",
                "parameters": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the expert model (options: 'deepseek', 'gemini', 'mimo', 'gemini_pro')",
                        "required": True,
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Detailed instructions for the expert model",
                        "required": True,
                    },
                    "file_paths": {
                        "type": "array",
                        "description": "List of file paths the expert model should analyze",
                        "required": False,
                    }
                },
                "returns": "Response from the expert model",
            },
        }
        
        return {
            "success": True,
            "result": tools,
            "message": f"Available tools: {len(tools)}",
        }


# Tool manager for coordinating tool execution
class ToolManager:
    """Manages tool execution and coordination."""
    
    def __init__(self):
        # Disable permission prompts for the backend daemon to prevent hanging
        self.basic_tools = BasicTools(require_permission=False)
        self.tool_registry = self._register_tools()
    
    def _register_tools(self) -> Dict[str, Any]:
        """Register all available tools."""
        return {
            "get_current_directory": self.basic_tools.get_current_directory,
            "list_files": self.basic_tools.list_files,
            "read_file": self.basic_tools.read_file,
            "write_file": self.basic_tools.write_file,
            "execute_command": self.basic_tools.execute_command,
            "calculate": self.basic_tools.calculate,
            "get_system_info": self.basic_tools.get_system_info,
            "web_search": self.basic_tools.web_search,
            "fetch_webpage": self.basic_tools.fetch_webpage,
            "ask_expert_model": self.basic_tools.ask_expert_model,
        }
    
    def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with parameters."""
        if tool_name not in self.tool_registry:
            return {
                "success": False,
                "result": None,
                "message": f"Tool not found: {tool_name}",
                "tool_name": tool_name,
            }
            
        # Convert WSL paths if needed before execution
        import platform
        import re
        if 'linux' in platform.system().lower() and 'microsoft' in platform.release().lower():
            for key in ['file_path', 'directory']:
                if key in parameters and isinstance(parameters[key], str):
                    p = parameters[key]
                    m = re.match(r'^([a-zA-Z]):[\\/](.*)$', p)
                    if m:
                        drive = m.group(1).lower()
                        rest = m.group(2).replace('\\', '/')
                        parameters[key] = f"/mnt/{drive}/{rest}"
        
        try:
            tool_func = self.tool_registry[tool_name]
            result = tool_func(**parameters)
            result["tool_name"] = tool_name
            result["parameters"] = parameters
            return result
            
        except TypeError as e:
            return {
                "success": False,
                "result": None,
                "message": f"Invalid parameters for {tool_name}: {e}",
                "tool_name": tool_name,
                "parameters": parameters,
            }
        except Exception as e:
            return {
                "success": False,
                "result": None,
                "message": f"Error executing {tool_name}: {e}",
                "tool_name": tool_name,
                "parameters": parameters,
            }
    
    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get schema for a specific tool."""
        tools_info = self.basic_tools.get_available_tools()
        if tools_info["success"]:
            return tools_info["result"].get(tool_name)
        return None
    
    def list_tools(self) -> Dict[str, Any]:
        """List all available tools."""
        return self.basic_tools.get_available_tools()

    def get_openai_tools_schema(self) -> list:
        """Get tools in OpenAI's JSON schema format."""
        schema_list = []
        tools_info = self.basic_tools.get_available_tools()
        if not tools_info["success"]:
            return []
            
        for tool_name, tool_def in tools_info["result"].items():
            parameters = {
                "type": "object",
                "properties": {},
                "required": []
            }
            
            for param_name, param_def in tool_def.get("parameters", {}).items():
                parameters["properties"][param_name] = {
                    "type": param_def.get("type", "string"),
                    "description": param_def.get("description", "")
                }
                if param_def.get("required", False):
                    parameters["required"].append(param_name)
                    
            schema_list.append({
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_def.get("description", ""),
                    "parameters": parameters
                }
            })
            
        return schema_list