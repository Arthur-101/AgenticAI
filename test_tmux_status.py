import subprocess
import time
import os
import pty

master, slave = pty.openpty()
p = subprocess.Popen(["tmux", "new-session", "-A", "-s", "test_pty_status"], stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

subprocess.run(["tmux", "set-option", "-t", "test_pty_status", "status", "off"])

time.sleep(0.5)
subprocess.run(["tmux", "kill-session", "-t", "test_pty_status"])
print("Done")
