import subprocess
import pty
import os
import time
import fcntl
import termios
import struct

master, slave = pty.openpty()
cmd = ["tmux", "new-session", "-A", "-s", "test_size2"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

# Emulate frontend resize
rows, cols = 40, 120
winsize = struct.pack("HHHH", rows, cols, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
subprocess.run(["tmux", "resize-window", "-t", "test_size2", "-x", str(cols), "-y", str(rows)])

subprocess.run(["tmux", "send-keys", "-t", "test_size2", "stty size > /tmp/tmux_size2.txt", "Enter"])
time.sleep(0.5)

with open("/tmp/tmux_size2.txt", "r") as f:
    print("Size inside tmux:", f.read().strip())

subprocess.run(["tmux", "kill-session", "-t", "test_size2"])
