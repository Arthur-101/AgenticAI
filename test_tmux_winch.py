import subprocess
import pty
import os
import time
import fcntl
import termios
import struct

master, slave = pty.openpty()
cmd = ["tmux", "new-session", "-A", "-s", "test_winch"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

# Emulate frontend resize
winsize = struct.pack("HHHH", 50, 150, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
time.sleep(0.5)

subprocess.run(["tmux", "send-keys", "-t", "test_winch", "stty size > /tmp/tmux_winch.txt", "Enter"])
time.sleep(0.5)

with open("/tmp/tmux_winch.txt", "r") as f:
    print("Size inside tmux after SIGWINCH:", f.read().strip())

subprocess.run(["tmux", "kill-session", "-t", "test_winch"])
