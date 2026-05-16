import asyncio
import websockets
import json

async def test_ws():
    async with websockets.connect("ws://127.0.0.1:8000/ws/terminal") as websocket:
        print("Connected!")
        await asyncio.sleep(2)
        
asyncio.run(test_ws())
