import pty
import subprocess
import time
import os

master, slave = pty.openpty()

cmd = ["tmux", "new-session", "-A", "-s", "test_scroll_2", ";", "set-option", "-t", "test_scroll_2", "status", "off", ";", "set-option", "-g", "mouse", "on"]
# We must set TERM to xterm-256color or similar so tmux knows it supports mouse
env = os.environ.copy()
env["TERM"] = "xterm-256color"
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env)
os.close(slave)

time.sleep(1)

res = subprocess.run(["tmux", "show-environment", "-g", "-t", "test_scroll_2"], capture_output=True, text=True)
print("Global Env:", res.stdout.strip())

res = subprocess.run(["tmux", "show-options", "-g", "mouse"], capture_output=True, text=True)
print("Mouse option:", res.stdout.strip())

subprocess.run(["tmux", "kill-session", "-t", "test_scroll_2"])
