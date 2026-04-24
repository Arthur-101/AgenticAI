"""Basic tools for the AI agent."""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import json


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
            
            # Read file
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
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
        self.basic_tools = BasicTools()
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