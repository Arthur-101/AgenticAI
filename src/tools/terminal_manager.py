import os
import pty
import subprocess
import threading
import fcntl
import termios
import struct
import select
import time
import re
import shlex
from typing import Callable, List, Optional, Dict, Any
import sys

class TerminalManager:
    """Manages a shared stateful terminal session using tmux for both user and AI agents."""
    
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
        self.session_name = "agenticai-shared"
        
        # Agent execution state
        self._agent_lock = threading.Lock()
        
    def start(self, workdir: str = "."):
        """Starts the terminal session using tmux."""
        if self.is_running:
            return
            
        if sys.platform != "win32":
            master_fd, slave_fd = pty.openpty()
            # We no longer disable ECHO so that user inputs are echoed correctly in the UI.

            cmd = ["tmux", "new-session", "-A", "-s", self.session_name]
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
            try:
                os.write(self.fd, data.encode("utf-8"))
            except OSError as e:
                print(f"Error writing to terminal: {e}", file=sys.stderr)
                self.stop()

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
                    
                    for callback in self.output_callbacks:
                        try:
                            callback(decoded_output)
                        except Exception as e:
                            print(f"Error in terminal callback: {e}", file=sys.stderr)
            except OSError as e:
                print(f"Terminal read error (likely closed): {e}", file=sys.stderr)
                self.is_running = False
                break
                
    def get_history(self, lines: int = 100) -> str:
        """Retrieves the recent history of the terminal using tmux capture-pane."""
        if not self.is_running:
            return ""
        try:
            res = subprocess.run(
                ["tmux", "capture-pane", "-p", "-J", "-S", f"-{lines}", "-t", self.session_name],
                capture_output=True, text=True, timeout=2
            )
            return res.stdout.strip()
        except Exception as e:
            return f"Error fetching history: {e}"

    def execute_agent_command(self, command: str, workdir: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Executes a command synchronously for an AI agent, enforcing OpenCode-style restrictions."""
        if not self.is_running:
            self.start()
            
        with self._agent_lock:
            delimiter_uuid = str(time.time()).replace(".", "")
            start_delim = f"---START---{delimiter_uuid}"
            end_delim = f"---END---{delimiter_uuid}"
            
            # Prepare command
            full_command = f"echo '{start_delim}'\n"
            if workdir:
                full_command += f"cd {shlex.quote(workdir)}\n"
            full_command += f"{command}\necho \"\n{end_delim}_$?\"\n"
            
            # Echo to the UI that an agent is running a command
            agent_msg = f"\r\n\x1b[36m[Agent Executing]:\x1b[0m {command}\r\n"
            for cb in self.output_callbacks:
                try:
                    cb(agent_msg)
                except Exception:
                    pass
                
            self.write(full_command)
            
            start_time = time.time()
            return_code = -1
            timed_out = False
            raw_output = ""
            
            while True:
                if time.time() - start_time > timeout:
                    timed_out = True
                    break
                    
                pane_content = self.get_history(lines=1000)
                
                start_occurrences = [m.start() for m in re.finditer(start_delim, pane_content)]
                end_match = re.search(f"{end_delim}_(\\d+)", pane_content)
                
                if start_occurrences and end_match:
                    return_code = int(end_match.group(1))
                    output_start = start_occurrences[-1] + len(start_delim)
                    raw_output = pane_content[output_start:end_match.start()].strip()
                    break
                    
                time.sleep(0.1)
                
            if timed_out:
                self.write("\x03")  # Send SIGINT
                return {
                    "success": False,
                    "result": {"stdout": "Command timed out.", "stderr": "", "returncode": -1},
                    "message": f"Command timed out after {timeout} seconds. Sent SIGINT.",
                }
                
            # Clean up the trailing echo command from the raw output if it exists
            lines = raw_output.split('\n')
            clean_lines = []
            for line in lines:
                if f"---END---{delimiter_uuid}" in line:
                    continue
                if line.strip() == ">" or line.strip() == 'echo "':
                    continue
                clean_lines.append(line)
                
            final_output = "\n".join(clean_lines).strip()
            
            max_len = 50000
            if len(final_output) > max_len:
                final_output = final_output[:max_len] + f"\n... [Output truncated to {max_len} bytes]"
                
            return {
                "success": return_code == 0,
                "result": {"stdout": final_output, "stderr": "", "returncode": return_code},
                "message": f"Command executed with return code: {return_code}",
            }

    def stop(self):
        """Stops the terminal session and cleans up resources."""
        self.is_running = False
        
        if self.process:
            try:
                # Kill the tmux session
                subprocess.run(["tmux", "kill-session", "-t", self.session_name], capture_output=True)
                self.process.terminate()
                self.process.wait(timeout=2)
            except Exception:
                pass
            self.process = None
            
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
            
terminal_manager = TerminalManager.get_instance()
