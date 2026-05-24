import pty
import subprocess
import time
import os
import fcntl
import termios
import struct

master, slave = pty.openpty()

# Start tmux
cmd = [
    "tmux", "new-session", "-A", "-s", "test_fit", 
    ";", "set-option", "-t", "test_fit", "status", "off",
    ";", "set-option", "-g", "mouse", "on",
    ";", "set-option", "-ga", "terminal-overrides", ",xterm*:smcup@:rmcup@"
]
env = os.environ.copy()
env["TERM"] = "xterm-256color"
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env)
os.close(slave)

time.sleep(1)

# Check size
res = subprocess.run(["tmux", "display-message", "-p", "#{window_width}x#{window_height}"], capture_output=True, text=True)
print("Initial size:", res.stdout.strip())

# Resize master
winsize = struct.pack("HHHH", 40, 120, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
time.sleep(0.5)

# Also explicitly resize window
subprocess.run(["tmux", "resize-window", "-t", "test_fit", "-x", "120", "-y", "40"])
time.sleep(0.5)

# Check size again
res = subprocess.run(["tmux", "display-message", "-p", "#{window_width}x#{window_height}"], capture_output=True, text=True)
print("Resized size:", res.stdout.strip())

subprocess.run(["tmux", "kill-session", "-t", "test_fit"])
