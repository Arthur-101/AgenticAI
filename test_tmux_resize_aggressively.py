import pty
import subprocess
import time
import os

master, slave = pty.openpty()

# Start tmux
cmd = [
    "tmux", "new-session", "-A", "-s", "test_agg_fit", 
    ";", "set-option", "-t", "test_agg_fit", "status", "off",
    ";", "set-option", "-g", "mouse", "on",
    ";", "set-window-option", "-t", "test_agg_fit", "aggressive-resize", "on"
]
env = os.environ.copy()
env["TERM"] = "xterm-256color"
p = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, env=env)
os.close(slave)

time.sleep(1)

res = subprocess.run(["tmux", "show-window-options", "-t", "test_agg_fit", "aggressive-resize"], capture_output=True, text=True)
print("Aggressive resize:", res.stdout.strip())

subprocess.run(["tmux", "kill-session", "-t", "test_agg_fit"])
