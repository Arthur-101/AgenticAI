import subprocess
import pty
import os
import time
import fcntl
import termios
import struct

master, slave = pty.openpty()

# Start at 24 columns
winsize = struct.pack("HHHH", 24, 24, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)

cmd = ["tmux", "new-session", "-A", "-s", "test_checkwinsize"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(1)

# Resize to 100 columns
rows, cols = 40, 100
winsize = struct.pack("HHHH", rows, cols, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
subprocess.run(["tmux", "resize-window", "-t", "test_checkwinsize", "-x", str(cols), "-y", str(rows)])
time.sleep(1)

# Run a command to trigger checkwinsize
subprocess.run(["tmux", "send-keys", "-t", "test_checkwinsize", "shopt | grep checkwinsize", "Enter"])
time.sleep(0.5)

res = subprocess.run(["tmux", "capture-pane", "-p", "-J", "-t", "test_checkwinsize"], capture_output=True, text=True)
print("Output:")
print(res.stdout)

subprocess.run(["tmux", "kill-session", "-t", "test_checkwinsize"])
