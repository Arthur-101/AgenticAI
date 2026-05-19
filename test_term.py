import sys, time
from src.tools.terminal_manager import terminal_manager

terminal_manager.start()

# Register a dummy callback so we get output
def cb(x): pass
terminal_manager.register_callback(cb)

time.sleep(1) # wait for bash to start

res = terminal_manager.execute_agent_command("ls")
print(f"Result (ls):\n{res['result']['stdout']}")

res2 = terminal_manager.execute_agent_command("echo hello world")
print(f"Result (echo):\n{res2['result']['stdout']}")
