import pty
import subprocess
import time
import os
import struct
import fcntl
import termios

master, slave = pty.openpty()

cmd = ["tmux", "new-session", "-A", "-s", "test_scroll", ";", "set-option", "-t", "test_scroll", "status", "off", ";", "set-option", "-g", "mouse", "on"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)

time.sleep(1)

# Resize to something normal
winsize = struct.pack("HHHH", 24, 80, 0, 0)
fcntl.ioctl(master, termios.TIOCSWINSZ, winsize)
subprocess.run(["tmux", "resize-window", "-t", "test_scroll", "-x", "80", "-y", "24"])

# Let's see what tmux show-options -g says about terminal overrides
res = subprocess.run(["tmux", "show-options", "-g", "terminal-overrides"], capture_output=True, text=True)
print("Terminal overrides:", res.stdout.strip())

# Clean up
subprocess.run(["tmux", "kill-session", "-t", "test_scroll"])
