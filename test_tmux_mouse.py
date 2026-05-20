import subprocess
import pty
import os
import time

master, slave = pty.openpty()
cmd = [
    "tmux", "new-session", "-A", "-s", "test_mouse", 
    ";", "set-option", "-t", "test_mouse", "status", "off",
    ";", "set-option", "-g", "mouse", "on"
]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)

time.sleep(0.5)

res = subprocess.run(["tmux", "show-options", "-g", "mouse"], capture_output=True, text=True)
print("Mouse option:", res.stdout.strip())

subprocess.run(["tmux", "kill-session", "-t", "test_mouse"])
