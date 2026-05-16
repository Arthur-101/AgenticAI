import asyncio
import websockets
import time

async def connect_and_wait():
    try:
        async with websockets.connect("ws://127.0.0.1:8000/ws/terminal") as ws:
            print("Successfully connected to websocket!")
            await asyncio.sleep(2)
    except Exception as e:
        print(f"Connection failed: {e}")

import sys
from src.api.embedded_backend import EmbeddedBackend
import threading

print("Initializing backend")
backend = EmbeddedBackend()
print("Waiting 3s for uvicorn to start")
time.sleep(3)
print("Testing connection")
asyncio.run(connect_and_wait())
