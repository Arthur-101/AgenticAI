import subprocess
import pty
import os
import time
import fcntl
import termios
import struct

master, slave = pty.openpty()
cmd = ["tmux", "new-session", "-A", "-s", "test_size"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

winsize = struct.pack("HHHH", 24, 80, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)

subprocess.run(["tmux", "send-keys", "-t", "test_size", "stty size > /tmp/tmux_size.txt", "Enter"])
time.sleep(0.5)

with open("/tmp/tmux_size.txt", "r") as f:
    print("Size inside tmux:", f.read().strip())

subprocess.run(["tmux", "kill-session", "-t", "test_size"])
