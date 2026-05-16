import threading
import uvicorn
import time
from fastapi import FastAPI

app = FastAPI()

def run():
    uvicorn.run(app, port=8001)

t = threading.Thread(target=run)
t.start()
time.sleep(2)
print("Done")
