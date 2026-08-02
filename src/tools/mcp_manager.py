import os
import sys
import json
import logging
import subprocess
import threading
import shutil
import platform
import atexit
from pathlib import Path
from collections import deque
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class McpClient:
    """Manages a single stdio-based MCP server subprocess, its handshake, tools, and logging."""

    def __init__(self, name: str, command: str, args: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.args = args
        self.env = env or {}
        self.process = None
        self.tools = []
        self.status = "Stopped" # Stopped, Active, Error
        self.error_message = ""
        
        # Log buffers for advanced UI display (keeps last 200 logs)
        self.logs = deque(maxlen=200)
        
        self._request_id = 1
        self._pending_requests = {} # id -> {"event": Event, "response": Dict}
        self._lock = threading.Lock()
        self._running = False
        
        self._stdout_thread = None
        self._stderr_thread = None

    def log(self, message: str):
        """Append a timestamped message to the circular log buffer."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")

    def start(self) -> bool:
        """Spawn the server process and execute the initial protocol handshake."""
        if self._running:
            return True

        self.log(f"Starting MCP server '{self.name}' using command: {self.command} {' '.join(self.args)}")
        try:
            # Merge system env with server specific env
            merged_env = os.environ.copy()
            merged_env.update(self.env)
            
            # Resolve executable or shell wrappers on Windows
            cmd_list = [self.command] + self.args
            if platform.system() == "Windows":
                resolved_cmd = shutil.which(self.command)
                if resolved_cmd:
                    cmd_list[0] = resolved_cmd
                # NPX/NPM/UVX on Windows needs execution via cmd shell wrapper
                if self.command in ["npm", "npx", "uvx", "pip"]:
                    cmd_list = ["cmd.exe", "/c", self.command] + self.args
            
            # Start process
            self.process = subprocess.Popen(
                cmd_list,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line buffered
                env=merged_env,
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            
            self._running = True
            
            # Start stdout and stderr background reading threads
            self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True, name=f"mcp-{self.name}-stdout")
            self._stdout_thread.start()
            
            self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True, name=f"mcp-{self.name}-stderr")
            self._stderr_thread.start()
            
            # 1. Initialize request
            if not self._initialize_handshake():
                self.status = "Error"
                self.error_message = "Handshake failed"
                self.stop()
                return False
                
            # 2. List tools
            self.tools = self._fetch_tools_catalog()
            self.status = "Active"
            self.error_message = ""
            self.log(f"Successfully connected to '{self.name}'. Registered {len(self.tools)} tools.")
            return True
            
        except Exception as e:
            self.status = "Error"
            self.error_message = str(e)
            self.log(f"Spawn error: {str(e)}")
            logger.error(f"Failed to start MCP server {self.name}: {e}")
            self._running = False
            return False

    def _read_stdout(self):
        """Read and dispatch JSON-RPC lines from server process stdout."""
        while self._running and self.process:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                
                stripped = line.strip()
                if not stripped:
                    continue
                    
                try:
                    msg = json.loads(stripped)
                    msg_id = msg.get("id")
                    
                    self.log(f"IN (stdout): {stripped[:200]}")
                    
                    if msg_id is not None:
                        with self._lock:
                            if msg_id in self._pending_requests:
                                self._pending_requests[msg_id]["response"] = msg
                                self._pending_requests[msg_id]["event"].set()
                except json.JSONDecodeError:
                    self.log(f"IN (stdout raw): {stripped}")
            except Exception as e:
                self.log(f"Stdout thread exception: {str(e)}")
                break
        self.log("Stdout thread terminated.")

    def _read_stderr(self):
        """Log diagnostics outputted by the server process stderr."""
        while self._running and self.process:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                self.log(f"ERR: {line.strip()}")
            except Exception:
                break
        self.log("Stderr thread terminated.")

    def _send_request(self, method: str, params: Dict[str, Any], timeout: float = 12.0) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and block waiting for matching response ID."""
        if not self._running or not self.process:
            return None
            
        with self._lock:
            req_id = self._request_id
            self._request_id += 1
            event = threading.Event()
            self._pending_requests[req_id] = {"event": event, "response": None}
            
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        
        req_str = json.dumps(req)
        self.log(f"OUT: {req_str[:200]}")
        
        try:
            self.process.stdin.write(req_str + "\n")
            self.process.stdin.flush()
        except Exception as e:
            self.log(f"Write error: {str(e)}")
            with self._lock:
                self._pending_requests.pop(req_id, None)
            return None
            
        if event.wait(timeout):
            with self._lock:
                req_data = self._pending_requests.pop(req_id, None)
                return req_data["response"] if req_data else None
        else:
            with self._lock:
                self._pending_requests.pop(req_id, None)
            self.log(f"Request timeout after {timeout} seconds")
            return None

    def _send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """Send a fire-and-forget JSON-RPC notification."""
        if not self._running or not self.process:
            return
        req = {
            "jsonrpc": "2.0",
            "method": method
        }
        if params is not None:
            req["params"] = params
            
        req_str = json.dumps(req)
        self.log(f"OUT (notify): {req_str[:200]}")
        try:
            self.process.stdin.write(req_str + "\n")
            self.process.stdin.flush()
        except Exception as e:
            self.log(f"Notification write error: {str(e)}")

    def _initialize_handshake(self) -> bool:
        """Complete the formal Model Context Protocol initialization sequence."""
        res = self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "AgenticAI-Host",
                "version": "1.0.0"
            }
        })
        if not res or "error" in res:
            self.log(f"Initialize rejected: {res}")
            return False
            
        self._send_notification("notifications/initialized")
        return True

    def _fetch_tools_catalog(self) -> List[Dict[str, Any]]:
        """Query the list of available tools from the server."""
        res = self._send_request("tools/list", {})
        if not res or "error" in res:
            self.log("Failed to load tools catalog")
            return []
        return res.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke a tool call on this server."""
        self.log(f"Invoking tool '{name}' with params: {arguments}")
        res = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        }, timeout=35.0)
        
        if not res:
            return {"success": False, "message": f"Timeout calling tool {name} on server {self.name}"}
        if "error" in res:
            return {"success": False, "message": res["error"].get("message", "Unknown server error")}
        return res.get("result", {})

    def stop(self):
        """Terminate process and close streams."""
        self._running = False
        self.status = "Stopped"
        if self.process:
            self.log("Stopping process...")
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=1.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self.tools = []


class McpManager:
    """Singleton manager that maintains server configurations and active subprocesses."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(McpManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.config_path = Path(os.getcwd()) / "data" / "mcp_config.json"
        self.clients: Dict[str, McpClient] = {}
        self.load_config_and_start()
        atexit.register(self.shutdown)
        self._initialized = True

    def load_config_and_start(self):
        """Read data/mcp_config.json and launch all enabled servers."""
        os.makedirs(self.config_path.parent, exist_ok=True)
        if not self.config_path.exists():
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"mcpServers": {}}, f, indent=2)
        
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read mcp_config.json: {e}")
            data = {"mcpServers": {}}

        servers = data.get("mcpServers", {})
        for name, cfg in servers.items():
            if cfg.get("enabled", True):
                client = McpClient(
                    name=name,
                    command=cfg.get("command", ""),
                    args=cfg.get("args", []),
                    env=cfg.get("env", {})
                )
                self.clients[name] = client
                # Spawn in background thread to avoid blocking main program startup
                threading.Thread(target=client.start, daemon=True).start()

    def get_all_servers(self) -> List[Dict[str, Any]]:
        """Return full configuration, status, and tools metadata of all servers."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"mcpServers": {}}
            
        servers_cfg = data.get("mcpServers", {})
        result = []
        for name, cfg in servers_cfg.items():
            client = self.clients.get(name)
            status = client.status if client else "Stopped"
            err_msg = client.error_message if client else ""
            tools = client.tools if client else []
            
            result.append({
                "name": name,
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "env": cfg.get("env", {}),
                "enabled": cfg.get("enabled", True),
                "status": status,
                "error_message": err_msg,
                "tools": tools
            })
        return result

    def get_logs(self, server_name: str) -> List[str]:
        """Return circular log lines for a specific server."""
        client = self.clients.get(server_name)
        return list(client.logs) if client else ["Server not running."]

    def add_server(self, name: str, command: str, args: List[str], env: Dict[str, str], enabled: bool = True) -> bool:
        """Write a new server config to disk and spin up the client process if enabled."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"mcpServers": {}}
            
        if "mcpServers" not in data:
            data["mcpServers"] = {}
            
        data["mcpServers"][name] = {
            "command": command,
            "args": args,
            "env": env,
            "enabled": enabled
        }
        
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        # If running old client, stop it
        if name in self.clients:
            self.clients[name].stop()
            
        if enabled:
            client = McpClient(name, command, args, env)
            self.clients[name] = client
            threading.Thread(target=client.start, daemon=True).start()
        else:
            self.clients.pop(name, None)
            
        return True

    def delete_server(self, name: str) -> bool:
        """Delete config from disk and terminate the running subprocess."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False
            
        if "mcpServers" in data and name in data["mcpServers"]:
            data["mcpServers"].pop(name)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                
        if name in self.clients:
            self.clients[name].stop()
            self.clients.pop(name)
            
        return True

    def execute_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Direct tool execution call to the target server."""
        client = self.clients.get(server_name)
        if not client or client.status != "Active":
            return {"success": False, "message": f"MCP Server '{server_name}' is not running or inactive."}
        return client.call_tool(tool_name, arguments)

    def shutdown(self):
        """Clean shutdown hook to stop all background processes on application exit."""
        logger.info("Shutting down all active MCP servers...")
        for client in list(self.clients.values()):
            try:
                client.stop()
            except Exception:
                pass
        self.clients.clear()

# Instantiate global manager
mcp_manager = McpManager()
