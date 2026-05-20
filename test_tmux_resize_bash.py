import subprocess
import pty
import os
import time
import fcntl
import termios
import struct

master, slave = pty.openpty()

# Start at 20 columns
winsize = struct.pack("HHHH", 24, 20, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)

cmd = ["tmux", "new-session", "-A", "-s", "test_bash_resize"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(1)

# Resize to 100 columns
rows, cols = 40, 100
winsize = struct.pack("HHHH", rows, cols, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
subprocess.run(["tmux", "resize-window", "-t", "test_bash_resize", "-x", str(cols), "-y", str(rows)])
time.sleep(1)

# Send 'ls -la'
subprocess.run(["tmux", "send-keys", "-t", "test_bash_resize", "ls -la"])
time.sleep(0.5)

res = subprocess.run(["tmux", "capture-pane", "-p", "-J", "-t", "test_bash_resize"], capture_output=True, text=True)
print("Output:")
print(res.stdout)

subprocess.run(["tmux", "kill-session", "-t", "test_bash_resize"])
