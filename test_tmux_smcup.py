import subprocess
import pty
import os
import time

master, slave = pty.openpty()
cmd = [
    "tmux", "new-session", "-A", "-s", "test_smcup", 
    ";", "set-option", "-t", "test_smcup", "status", "off",
    ";", "set-option", "-ga", "terminal-overrides", ",xterm*:smcup@:rmcup@"
]
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave)
os.close(slave)

time.sleep(0.5)

subprocess.run(["tmux", "kill-session", "-t", "test_smcup"])
