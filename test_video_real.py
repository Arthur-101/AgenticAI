import os
import httpx
import base64
from src.utils.config import config

video_path = "/mnt/f/Snipping/Screen Recording 2026-05-24 204848.mp4"
if not os.path.exists(video_path):
    print("Video file not found")
else:
    print(f"Video size: {os.path.getsize(video_path)}")

    try:
        with open(video_path, "rb") as f:
            # Read the whole file properly instead of truncating
            encoded = base64.b64encode(f.read()).decode('utf-8')
            
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "What is happening in this short video?"},
                {"type": "image_url", "image_url": {"url": f"data:video/mp4;base64,{encoded}"}}
            ]}
        ]
        
        response = httpx.post(
            f"{config.settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {config.settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash-lite",
                "messages": messages,
                "max_tokens": 100
            },
            timeout=30
        )
        print(response.status_code)
        print(response.text)
    except Exception as e:
        print(e)
