import mimetypes
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from chainlit.utils import mount_chainlit

# The slim Docker image has no /etc/mime.types and Python's built-in table
# doesn't know these, so the fonts would otherwise be served as text/plain.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/webp", ".webp")

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "public")
LANDING_PATH = os.path.join(os.path.dirname(__file__), "landing_zine.html")
OG_IMAGE_PATH = os.path.join(PUBLIC_DIR, "og-image.png")

# Nothing this app legitimately receives comes anywhere near this. Without a
# cap, one large request body is read into memory whole, and the free host
# has 512 MB.
MAX_BODY_BYTES = 1_000_000

# File upload is disabled in .chainlit/config.toml, but Chainlit reads the
# whole uploaded file before it checks that setting. Refuse it at the door.
BLOCKED_ROUTES = {("POST", "/chat/project/file")}

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
]


async def _reject(send, status: int):
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"text/plain"), (b"content-length", b"0"), *SECURITY_HEADERS]})
    await send({"type": "http.response.body", "body": b""})


class RequestGuard:
    """Turns away oversized and blocked requests before any body is read, and
    adds two security headers to every response. Plain ASGI rather than
    FastAPI middleware so it never buffers a request and leaves the chat's
    websocket untouched."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        if (scope["method"], scope["path"].rstrip("/")) in BLOCKED_ROUTES:
            return await _reject(send, 404)

        headers = dict(scope["headers"])
        if b"chunked" in headers.get(b"transfer-encoding", b"").lower():
            # Browsers always send a length for the bodies this app accepts,
            # and a stream with no length can't be checked against the cap.
            return await _reject(send, 411)
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await _reject(send, 400)
        if length > MAX_BODY_BYTES:
            return await _reject(send, 413)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in SECURITY_HEADERS if k not in existing]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)


class CachedStaticFiles(StaticFiles):
    """The landing page's fonts never change, so browsers keep them for a
    year. Screenshots can be recaptured, so they are only kept for an hour
    and then revalidated against their ETag."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        path = str(args[0]) if args else ""
        response.headers.setdefault(
            "cache-control",
            "public, max-age=31536000, immutable" if path.endswith(".woff2") else "public, max-age=3600",
        )
        return response


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

# Self-hosted fonts and the real app screenshots used by the landing page.
app.mount("/static", CachedStaticFiles(directory=PUBLIC_DIR), name="static")


@app.api_route("/", methods=["GET", "HEAD"])
async def landing():
    # no-cache means "check before reusing", so an updated page shows up on
    # the next visit instead of whenever a cached copy happens to expire.
    return FileResponse(LANDING_PATH, headers={"cache-control": "no-cache"})


@app.api_route("/favicon.ico", methods=["GET", "HEAD"])
async def favicon():
    # Browsers and crawlers ask for this at the root whatever the page says.
    return FileResponse(os.path.join(PUBLIC_DIR, "favicon.ico"), media_type="image/x-icon",
                        headers={"cache-control": "public, max-age=86400"})


@app.get("/v2")
async def landing_v2_redirect():
    # /v2 was the temporary comparison route while the design was in review.
    # Anyone who saved that link lands on the real page instead of a 404.
    return RedirectResponse("/", status_code=301)


@app.api_route("/og-image.png", methods=["GET", "HEAD"])
async def og_image():
    # Served at the site root so the Open Graph <meta> tag can point at an
    # absolute URL that link crawlers (LinkedIn, etc.) can fetch.
    return FileResponse(OG_IMAGE_PATH, media_type="image/png", headers={"cache-control": "public, max-age=86400"})


mount_chainlit(app=app, target="chainlit_app/app.py", path="/chat")

app.add_middleware(RequestGuard)
