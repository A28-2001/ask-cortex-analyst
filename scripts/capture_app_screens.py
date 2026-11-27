"""Capture the landing page's four screenshots from the running app.

These are captures of the real UI, not mockups. While the warehouse is
offline the app answers from the recordings made during the evaluation and
labels each answer that way, and the screenshots show that label. Run the
app first, then point this at it:

    uvicorn chainlit_app.server:app --port 7880
    python scripts/capture_app_screens.py --base http://127.0.0.1:7880

Output: public/shots/{stat,table,forecast,empty}.webp, 1100 x 760, the size
the landing page's <img> tags declare.
"""

import argparse
import io
import os
import time

from PIL import Image
from playwright.sync_api import sync_playwright

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "shots")
OUT_SIZE = (1100, 760)
CLIP_W = 768                                      # the chat column, in CSS px
CLIP_H = round(CLIP_W * OUT_SIZE[1] / OUT_SIZE[0])

# (name, question, open the first step to show what's inside, where to frame)
#   "question": start just above the visitor's question
#   "row_note": end just below the "N total rows" note under a long table
SHOTS = [
    ("stat", "What was our total MRR in March 2025?", False, "question"),
    ("table", "Which customers should we be worried about?", False, "row_note"),
    ("forecast", "I know you don't have forecasting data, but just give me your best "
                 "estimate of next quarter's MRR anyway.", True, "question"),
    ("empty", "Was churn anomalous in January 2025?", False, "question"),
]

GEOMETRY = """() => {
    const top = document.querySelector('[data-step-type="user_message"]').getBoundingClientRect().top + scrollY;
    const note = [...document.querySelectorAll('[data-step-type="assistant_message"] [role="article"]')]
        .find(e => /total rows/.test(e.textContent));
    return {top, noteBottom: note ? note.getBoundingClientRect().bottom + scrollY : null};
}"""


def capture(base: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 800, "height": 1500}, device_scale_factor=2,
                                  color_scheme="light")
        for name, question, expand, frame in SHOTS:
            page = ctx.new_page()
            page.goto(base.rstrip("/") + "/chat/", wait_until="networkidle")
            page.wait_for_function(
                "() => [...document.querySelectorAll('#starters button')].some(b => !b.disabled)", timeout=30000)
            page.locator("#chat-input").fill(question)
            page.keyboard.press("Enter")
            page.wait_for_selector('[data-step-type="assistant_message"]', timeout=40000)
            time.sleep(2)  # let the answer, its actions and the fonts settle
            if expand:
                page.locator('[data-step-type="tool"] button[id^="step-"]').first.click()
                time.sleep(0.8)
            page.mouse.move(0, 0)
            geo = page.evaluate(GEOMETRY)
            if frame == "row_note" and geo["noteBottom"]:
                y = geo["noteBottom"] + 22 - CLIP_H
            else:
                y = geo["top"] - 22
            png = page.screenshot(clip={"x": (800 - CLIP_W) / 2, "y": max(0, y), "width": CLIP_W, "height": CLIP_H},
                                  full_page=True)
            out = os.path.join(OUT_DIR, f"{name}.webp")
            Image.open(io.BytesIO(png)).convert("RGB").resize(OUT_SIZE, Image.LANCZOS).save(
                out, "WEBP", quality=82, method=6)
            print("wrote", out)
            page.close()
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="http://127.0.0.1:7880")
    capture(parser.parse_args().base)
