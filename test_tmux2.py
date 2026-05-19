import subprocess
import time
import os
import pty
import re
import shlex

master, slave = pty.openpty()
p = subprocess.Popen(["tmux", "new-session", "-A", "-s", "test_pty2"], stdin=slave, stdout=slave, stderr=slave)
os.close(slave)
time.sleep(0.5)

delim_uuid = "12345"
start_delim = f"---START---{delim_uuid}"
end_delim = f"---END---{delim_uuid}"

cmd = f"echo '{start_delim}'\ncd /tmp\npwd\necho \"\n{end_delim}_$?\"\n"
os.write(master, cmd.encode())

time.sleep(1)

res = subprocess.run(["tmux", "capture-pane", "-p", "-J", "-S", "-1000", "-t", "test_pty2"], capture_output=True, text=True)
pane_content = res.stdout

print("PANE CONTENT:")
print("-------------")
print(pane_content)
print("-------------")

start_occurrences = [m.start() for m in re.finditer(start_delim, pane_content)]
end_match = re.search(f"{end_delim}_(\\d+)", pane_content)

if start_occurrences and end_match:
    output_start = start_occurrences[-1] + len(start_delim)
    raw_output = pane_content[output_start:end_match.start()].strip()
    print("EXTRACTED RAW:")
    print(raw_output)

subprocess.run(["tmux", "kill-session", "-t", "test_pty2"])
