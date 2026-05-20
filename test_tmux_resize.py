import subprocess
import pty
import os
import time

master, slave = pty.openpty()
cmd = [
    "tmux", "new-session", "-A", "-s", "test_resize", 
    ";", "set-option", "-t", "test_resize", "status", "off"
]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

import fcntl
import termios
import struct
winsize = struct.pack("HHHH", 40, 100, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
time.sleep(0.5)

# Also force tmux to resize window specifically
subprocess.run(["tmux", "resize-window", "-t", "test_resize", "-x", "100", "-y", "40"])
time.sleep(0.5)

subprocess.run(["tmux", "kill-session", "-t", "test_resize"])
print("Resize test done")
