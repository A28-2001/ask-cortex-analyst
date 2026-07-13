import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

from chainlit.utils import mount_chainlit

app = FastAPI()

LANDING_PATH = os.path.join(os.path.dirname(__file__), "landing.html")


@app.get("/")
async def landing():
    return FileResponse(LANDING_PATH)


mount_chainlit(app=app, target="chainlit_app/app.py", path="/chat")
