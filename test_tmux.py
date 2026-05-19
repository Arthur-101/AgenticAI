import subprocess
import time

# Start a tmux session detached
subprocess.run(["tmux", "new-session", "-d", "-s", "test_sess"])

# Send a command
subprocess.run(["tmux", "send-keys", "-t", "test_sess", "echo hello world; sleep 1; echo done_123", "Enter"])

# Wait for it to finish by monitoring capture-pane
for _ in range(30):
    res = subprocess.run(["tmux", "capture-pane", "-p", "-t", "test_sess"], capture_output=True, text=True)
    if "done_123" in res.stdout:
        print("Found it! Output:")
        print(res.stdout)
        break
    time.sleep(0.1)

# Cleanup
subprocess.run(["tmux", "kill-session", "-t", "test_sess"])
