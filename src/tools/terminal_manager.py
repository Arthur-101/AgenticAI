import os
import subprocess
import threading
import time
import re
import shlex
from typing import Callable, List, Optional, Dict, Any
import sys

# Linux-only imports
if sys.platform != "win32":
    import pty
    import fcntl
    import termios
    import struct
    import select

class TerminalManager:
    """Manages a shared stateful terminal session using tmux (Linux) or pywinpty (Windows) for both user and AI agents."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.fd: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.winpty_proc = None
        self.win_history = ""
        self.output_callbacks: List[Callable[[str], None]] = []
        self._read_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.session_name = "agenticai-shared"
        
        # Agent execution state
        self._agent_lock = threading.Lock()
        
    def start(self, workdir: str = "."):
        """Starts the terminal session using tmux or pywinpty."""
        if self.is_running:
            return
            
        if sys.platform != "win32":
            master_fd, slave_fd = pty.openpty()

            cmd = [
                "tmux", "new-session", "-A", "-s", self.session_name, 
                ";", "set-option", "-t", self.session_name, "status", "off",
                ";", "set-option", "-g", "mouse", "on",
                ";", "set-window-option", "-t", self.session_name, "aggressive-resize", "on"
            ]
            env = os.environ.copy()
            # Explicitly set TERM so tmux knows mouse scrolling is supported
            env["TERM"] = "xterm-256color"
            
            self.process = subprocess.Popen(
                cmd,
                preexec_fn=os.setsid,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=workdir,
                env=env
            )
            os.close(slave_fd)
            self.fd = master_fd
            
            flags = fcntl.fcntl(self.fd, fcntl.F_GETFL)
            fcntl.fcntl(self.fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            self.is_running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            
        else:
            import winpty
            self.winpty_proc = winpty.PTY(80, 24)
            # Spawn powershell
            self.winpty_proc.spawn(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", cwd=workdir)
            
            self.is_running = True
            self.win_history = ""
            self._read_thread = threading.Thread(target=self._read_loop_win, daemon=True)
            self._read_thread.start()
            
    def resize(self, rows: int, cols: int):
        """Resizes the PTY terminal."""
        if sys.platform != "win32":
            if self.fd:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
                if self.is_running:
                    try:
                        # Also explicitly tell tmux to resize to avoid wrapping issues
                        subprocess.run(["tmux", "resize-window", "-t", self.session_name, "-x", str(cols), "-y", str(rows)], capture_output=True)
                    except Exception:
                        pass
        else:
            if self.winpty_proc:
                self.winpty_proc.set_size(cols, rows)

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
        if not self.is_running:
            self.start()
            
        if sys.platform != "win32":
            if self.fd is not None:
                try:
                    os.write(self.fd, data.encode("utf-8"))
                except OSError as e:
                    print(f"Error writing to terminal: {e}", file=sys.stderr)
                    self.stop()
        else:
            if self.winpty_proc:
                try:
                    self.winpty_proc.write(data)
                except Exception as e:
                    print(f"Error writing to pywinpty: {e}", file=sys.stderr)
                    self.stop()

    def _read_loop(self):
        """Continuously reads from the PTY and triggers callbacks (Linux)."""
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
                
    def _read_loop_win(self):
        """Continuously reads from the PTY and triggers callbacks (Windows)."""
        while self.is_running and self.winpty_proc:
            try:
                output = self.winpty_proc.read(blocking=False)
                if output:
                    self.win_history += output
                    if len(self.win_history) > 100000:
                        self.win_history = self.win_history[-50000:]
                        
                    for callback in self.output_callbacks:
                        try:
                            callback(output)
                        except Exception as e:
                            print(f"Error in terminal callback: {e}", file=sys.stderr)
                else:
                    time.sleep(0.01)
            except Exception as e:
                if "PTY closed" not in str(e):
                    print(f"Windows PTY read error: {e}", file=sys.stderr)
                self.is_running = False
                break

    @staticmethod
    def clean_ansi(text: str) -> str:
        """Strips ANSI escape codes, collapses PSReadLine repaints, and returns clean visual terminal text for LLMs."""
        if not text:
            return ""
            
        lines_raw = text.split('\n')
        cleaned_lines = []
        
        for raw in lines_raw:
            sub_segments = re.split(r'\x1b\[[0-9]+;[0-9]+[Hf]|\x1b\[[0-9]*[KGJ]|\r', raw)
            clean_sub = []
            for seg in sub_segments:
                s = re.sub(r'\x1b\][^\x07\x1b]*(\x07|\x1b\\)', '', seg)
                s = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', s)
                s = re.sub(r'\x1b[@-Z\\-_]', '', s)
                s = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', s).strip()
                if s:
                    clean_sub.append(s)
                    
            if not clean_sub:
                continue
                
            first_seg = clean_sub[0]
            last_seg = clean_sub[-1]
            
            if '>' in first_seg and not '>' in last_seg:
                prompt_part = first_seg.split('>')[0] + '>'
                final_line = f'{prompt_part} {last_seg}'
            else:
                final_line = last_seg
                
            cleaned_lines.append(final_line)
            
        # Group consecutive lines sharing the SAME prompt prefix (e.g. 'PS E:\Codes\AgenticAI\z_DebugImages>')
        # and keep ONLY the LAST line in each group (the completed input right before Enter)
        final_output = []
        i = 0
        while i < len(cleaned_lines):
            curr = cleaned_lines[i]
            if '>' in curr or 'PS ' in curr:
                prompt_prefix = curr.split('>')[0] if '>' in curr else curr[:10]
                j = i
                while j + 1 < len(cleaned_lines) and ('>' in cleaned_lines[j+1] or 'PS ' in cleaned_lines[j+1]) and cleaned_lines[j+1].split('>')[0] == prompt_prefix:
                    j += 1
                final_output.append(cleaned_lines[j])
                i = j + 1
            else:
                final_output.append(curr)
                i += 1
                
        return '\n'.join(final_output)

    def get_history(self, lines: int = 100, clean: bool = True) -> str:
        """Retrieves the recent history of the terminal."""
        if not self.is_running:
            return ""
            
        if sys.platform != "win32":
            try:
                res = subprocess.run(
                    ["tmux", "capture-pane", "-p", "-J", "-S", f"-{lines}", "-t", self.session_name],
                    capture_output=True, text=True, timeout=2
                )
                raw_text = res.stdout.strip()
            except Exception as e:
                return f"Error fetching history: {e}"
        else:
            history_lines = self.win_history.splitlines()
            raw_text = "\n".join(history_lines[-lines:])

        if clean:
            return self.clean_ansi(raw_text)
        return raw_text

    def execute_agent_command(self, command: str, workdir: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """Executes a command synchronously for an AI agent."""
        if not self.is_running:
            self.start()
            
        with self._agent_lock:
            delimiter_uuid = str(time.time()).replace(".", "")
            start_delim = f"---START---{delimiter_uuid}"
            end_delim = f"---END---{delimiter_uuid}"
            
            # Prepare command based on platform
            if sys.platform != "win32":
                full_command = f"echo '{start_delim}'\n"
                if workdir:
                    full_command += f"cd {shlex.quote(workdir)}\n"
                full_command += f"{command}\necho \"\n{end_delim}_$?\"\n"
            else:
                full_command = f"echo '{start_delim}'\r\n"
                if workdir:
                    full_command += f"Set-Location -LiteralPath '{workdir}'\r\n"
                full_command += f"{command}\r\n"
                full_command += f"$exitCode = $LASTEXITCODE; if ($null -eq $exitCode) {{ $exitCode = if ($?) {{ 0 }} else {{ 1 }} }}; echo \"`r`n{end_delim}_$exitCode\"\r\n"
            
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
                if sys.platform != "win32":
                    self.write("\x03")  # Send SIGINT (Ctrl+C)
                else:
                    self.write("\x03")
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
                if line.strip() == ">" or line.strip() == 'echo "' or "LASTEXITCODE" in line or start_delim in line:
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
        
        if sys.platform != "win32":
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
        else:
            if self.winpty_proc:
                try:
                    del self.winpty_proc
                except Exception:
                    pass
                self.winpty_proc = None

terminal_manager = TerminalManager.get_instance()
