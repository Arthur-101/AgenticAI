import subprocess
import pty
import os
import time
import fcntl
import termios
import struct

master, slave = pty.openpty()

# Set initial size to something small
winsize = struct.pack("HHHH", 24, 80, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)

cmd = ["tmux", "new-session", "-A", "-s", "test_size3"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

# Now try to resize to something big
rows, cols = 40, 120
winsize = struct.pack("HHHH", rows, cols, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
time.sleep(0.1)
# Try resize-window
res = subprocess.run(["tmux", "resize-window", "-t", "test_size3", "-x", str(cols), "-y", str(rows)], capture_output=True, text=True)

subprocess.run(["tmux", "send-keys", "-t", "test_size3", "stty size > /tmp/tmux_size3.txt", "Enter"])
time.sleep(0.5)

with open("/tmp/tmux_size3.txt", "r") as f:
    print("Size inside tmux after resize-window:", f.read().strip())

subprocess.run(["tmux", "kill-session", "-t", "test_size3"])
