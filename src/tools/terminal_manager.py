import os
import pty
import subprocess
import threading
import fcntl
import termios
import struct
import select
import asyncio
from typing import Callable, List, Optional
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
        
    def start(self, cmd: str = "/bin/bash", workdir: str = "."):
        """Starts the terminal session."""
        if self.is_running:
            return
            
        if sys.platform != "win32":
            # Unix-like system
            master_fd, slave_fd = pty.openpty()
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
            
            # Make the master_fd non-blocking
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
        """Writes data (commands) to the terminal."""
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
                    output = os.read(self.fd, 1024)
                    if not output:
                        self.is_running = False
                        break
                        
                    decoded_output = output.decode("utf-8", errors="replace")
                    for callback in self.output_callbacks:
                        try:
                            callback(decoded_output)
                        except Exception as e:
                            print(f"Error in terminal callback: {e}")
            except OSError as e:
                # If EOF is reached or other OS error
                self.is_running = False
                break
                
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
