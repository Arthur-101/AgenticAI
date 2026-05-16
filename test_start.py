import sys
from src.api.embedded_backend import EmbeddedBackend
print("Starting backend")
try:
    backend = EmbeddedBackend()
    import time
    time.sleep(3)
except Exception as e:
    import traceback
    traceback.print_exc()
