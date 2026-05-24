import asyncio
import websockets
import json

async def test():
    uri = "ws://127.0.0.1:8000/ws/terminal"
    async with websockets.connect(uri) as websocket:
        print("Connected")
        # Read the initial "Connected to AgenticAI Terminal" message
        msg1 = await websocket.recv()
        print("Received:", repr(msg1))
        
        # Send resize
        await websocket.send(json.dumps({"type": "resize", "rows": 40, "cols": 120}))
        
        # Send input
        await websocket.send(json.dumps({"type": "input", "data": "ls\n"}))
        
        # Read a few more messages
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                print("Received:", repr(msg))
            except asyncio.TimeoutError:
                break

asyncio.run(test())
