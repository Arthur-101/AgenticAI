import subprocess
import pty
import os

master, slave = pty.openpty()
p = subprocess.Popen(["tmux", "new-session", "-A", "-s", "test_multi", ";", "set-option", "-t", "test_multi", "status", "off"], stdin=slave, stdout=slave, stderr=slave)
os.close(slave)

import time
time.sleep(0.5)

res = subprocess.run(["tmux", "show-options", "-t", "test_multi", "status"], capture_output=True, text=True)
print("Status option:", res.stdout.strip())

subprocess.run(["tmux", "kill-session", "-t", "test_multi"])
