import pty
import subprocess
import time
import os

master, slave = pty.openpty()

cmd = ["tmux", "new-session", "-A", "-s", "test_scroll_3", ";", "set-option", "-t", "test_scroll_3", "status", "off", ";", "set-option", "-g", "mouse", "on"]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

subprocess.run(["tmux", "send-keys", "-t", "test_scroll_3", "echo 'hello world'", "Enter"])
time.sleep(0.5)

res = subprocess.run(["tmux", "capture-pane", "-p", "-t", "test_scroll_3"], capture_output=True, text=True)
print("Output:\n", res.stdout)

subprocess.run(["tmux", "kill-session", "-t", "test_scroll_3"])
