import os

from fastapi import FastAPI
from fastapi.responses import FileResponse

from chainlit.utils import mount_chainlit

app = FastAPI()

LANDING_PATH = os.path.join(os.path.dirname(__file__), "landing.html")
LANDING_V2_PATH = os.path.join(os.path.dirname(__file__), "landing_v2.html")
OG_IMAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "public", "og-image.png")


@app.get("/")
async def landing():
    return FileResponse(LANDING_PATH)


@app.get("/v2")
async def landing_v2():
    # Candidate redesign, served alongside the current page for comparison.
    return FileResponse(LANDING_V2_PATH)


@app.get("/og-image.png")
async def og_image():
    # Served at the site root so the Open Graph <meta> tag can point at an
    # absolute URL that link crawlers (LinkedIn, etc.) can fetch.
    return FileResponse(OG_IMAGE_PATH, media_type="image/png")


mount_chainlit(app=app, target="chainlit_app/app.py", path="/chat")
