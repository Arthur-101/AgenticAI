import os
import pty
import subprocess
import threading
import fcntl
import termios
import struct
import select
import asyncio
import time
import re
from typing import Callable, List, Optional, Tuple, Dict, Any
import sys

class TerminalManager:
    """Manages a shared stateful terminal session for both user and AI agents."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.output_callbacks: List[Callable[[str], None]] = []
        self._read_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # Agent execution state
        self._agent_lock = threading.Lock()
        self._current_agent_buffer = ""
        self._waiting_for_agent = False
        self._agent_delimiter = "---OPENDELIM---"
        
    def start(self, cmd: str = "/bin/bash", workdir: str = "."):
        """Starts the terminal session."""
        if self.is_running:
            return
            
        if sys.platform != "win32":
            master_fd, slave_fd = pty.openpty()
            # Disable echo on the slave so we don't read back our own commands when the agent runs them
            attrs = termios.tcgetattr(slave_fd)
            attrs[3] = attrs[3] & ~termios.ECHO
            termios.tcsetattr(slave_fd, termios.TCSANOW, attrs)

            self.process = subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=workdir,
                env=os.environ.copy()
            )
            os.close(slave_fd)
            self.fd = master_fd
            
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            self.is_running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            
            # Send initial command to set prompt and disable history so agent commands aren't saved
            self.write("export PS1='\\u@\\h:\\w$ '\n")
        else:
            raise NotImplementedError("Windows PTY support requires pywinpty. Fallback not implemented.")
            
    def resize(self, rows: int, cols: int):
        """Resizes the PTY terminal."""
        if self.fd and sys.platform != "win32":
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    def register_callback(self, callback: Callable[[str], None]):
        """Registers a callback to receive terminal output."""
        if callback not in self.output_callbacks:
            self.output_callbacks.append(callback)
            
    def unregister_callback(self, callback: Callable[[str], None]):
        """Unregisters an output callback."""
        if callback in self.output_callbacks:
            self.output_callbacks.remove(callback)

    def write(self, data: str):
        """Writes data to the terminal."""
        if not self.is_running or self.fd is None:
            self.start()
            
        if self.fd is not None:
            os.write(self.fd, data.encode("utf-8"))

    def _read_loop(self):
        """Continuously reads from the PTY and triggers callbacks."""
        while self.is_running and self.fd is not None:
            try:
                r, _, _ = select.select([self.fd], [], [], 0.1)
                if self.fd in r:
                    output = os.read(self.fd, 4096)
                    if not output:
                        self.is_running = False
                        break
                        
                    decoded_output = output.decode("utf-8", errors="replace")
                    
                    if self._waiting_for_agent:
                        self._current_agent_buffer += decoded_output
                        
                    for callback in self.output_callbacks:
                        try:
                            callback(decoded_output)
                        except Exception as e:
                            print(f"Error in terminal callback: {e}")
            except OSError as e:
                self.is_running = False
                break

    def execute_agent_command(self, command: str, workdir: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Executes a command synchronously for an AI agent, enforcing OpenCode-style restrictions."""
        import sys
        print(f"DEBUG: execute_agent_command called with '{command}' in terminal instance {id(self)}", file=sys.stderr, flush=True)
        print(f"DEBUG: callbacks registered: {len(self.output_callbacks)}", file=sys.stderr, flush=True)
        if not self.is_running:
            print("DEBUG: starting terminal manager", file=sys.stderr, flush=True)
            self.start()
            
        with self._agent_lock:
            self._waiting_for_agent = True
            self._current_agent_buffer = ""
            
            # Prepare the command payload
            # 1. Change directory if requested
            # 2. Run command
            # 3. Echo delimiter with exit code
            delimiter_uuid = str(time.time()).replace(".", "")
            delim = f"{self._agent_delimiter}{delimiter_uuid}"
            
            full_command = ""
            if workdir:
                full_command += f"cd '{workdir}'\n"
            
            # Execute command directly (no subshell) to preserve environment variables
            full_command += f"{command}\necho \"\n{delim}_$?\"\n"
            
            # Echo to the UI that an agent is running a command
            agent_msg = f"\r\n\x1b[36m[Agent Executing]:\x1b[0m {command}\r\n"
            for cb in self.output_callbacks:
                cb(agent_msg)
                
            self.write(full_command)
            
            start_time = time.time()
            return_code = -1
            timed_out = False
            
            # Wait for delimiter or timeout
            while True:
                if time.time() - start_time > timeout:
                    timed_out = True
                    break
                    
                if re.search(f"{delim}_(\\d+)", self._current_agent_buffer):
                    break
                    
                time.sleep(0.1)
                
            # We need to strip out the echoed command from the buffer, 
            # as PTYs echo stdin to stdout by default.
            
            # The command we sent was echoed back to us (potentially with ANSI codes)
            # Find the position of our delimiter output
            delim_match = re.search(f"{delim}_(\\d+)", self._current_agent_buffer)
            if delim_match:
                return_code = int(delim_match.group(1))
                
                # Everything before the delimiter output is our buffer
                raw_output = self._current_agent_buffer[:delim_match.start()]
                
                # The raw_output will contain:
                # 1. The echoed cd command (if any)
                # 2. The output of the cd command (if any)
                # 3. The echoed actual command
                # 4. The actual output
                # 5. The echoed echo command
                
                # Split by lines
                lines = raw_output.split("\n")
                
                # Filter out the lines that are just our commands being echoed
                # Also strip carriage returns from the end of lines
                clean_lines = []
                cmd_parts = command.split('\n')
                for line in lines:
                    line_clean = line.strip('\r')
                    
                    # Skip empty lines at the very beginning
                    if not line_clean and not clean_lines:
                        continue
                        
                    # Simple heuristic: if the line exactly matches part of our command, 
                    # or the cd command, or the echo command, skip it
                    is_echo = False
                    if line_clean == f"cd '{workdir}'":
                        is_echo = True
                    elif line_clean.startswith(f"echo \"\n{self._agent_delimiter}"):
                        is_echo = True
                    else:
                        for part in cmd_parts:
                            if part and line_clean.endswith(part):
                                is_echo = True
                                break
                                
                    if not is_echo:
                        clean_lines.append(line_clean)
                        
                output = "\n".join(clean_lines).strip()
                
                # Finally, strip any ANSI escape sequences that might have leaked through
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                output = ansi_escape.sub('', output).strip()
            else:
                # If we timed out
                output = "Command timed out."
                return_code = -1
            
            if len(output) > max_len:
                output = output[:max_len] + f"\n... [Output truncated to {max_len} bytes]"
                
            self._waiting_for_agent = False
            self._current_agent_buffer = ""
            
            if timed_out:
                # If timed out, try to send Ctrl+C to interrupt
                self.write("\x03")
                return {
                    "success": False,
                    "result": {"stdout": output, "stderr": "", "returncode": -1},
                    "message": f"Command timed out after {timeout} seconds. Sent SIGINT.",
                }
                
            return {
                "success": return_code == 0,
                "result": {"stdout": output, "stderr": "", "returncode": return_code},
                "message": f"Command executed with return code: {return_code}",
            }

    def stop(self):
        """Stops the terminal session."""
        self.is_running = False
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
            
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            
terminal_manager = TerminalManager.get_instance()
