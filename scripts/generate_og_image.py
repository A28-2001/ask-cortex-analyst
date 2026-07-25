"""Render the 1200x630 Open Graph / LinkedIn preview card.

The card is authored as HTML (public/og-card.html) so it uses the same
self hosted fonts and palette as the landing page itself, then rendered to
PNG with a real browser. Keeping it as HTML means the card cannot drift out
of sync with the site's visual language.

Run the app first, then:

    uvicorn chainlit_app.server:app --port 7880
    python scripts/generate_og_image.py --base http://127.0.0.1:7880

Output: public/og-image.png
"""

import argparse
import os

from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), "..", "public", "og-image.png")


def render(base_url: str):
    url = base_url.rstrip("/") + "/static/og-card.html"
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        # deviceScaleFactor 1: Open Graph wants exactly 1200x630.
        ctx = browser.new_context(
            viewport={"width": 1200, "height": 630}, device_scale_factor=1
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(900)
        page.screenshot(path=OUT)
        browser.close()
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:7880")
    args = ap.parse_args()
    render(args.base)
