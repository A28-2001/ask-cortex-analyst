"""Capture real screenshots of the running assistant for the landing page.

These are genuine captures of the deployed UI answering real questions against
Snowflake, not mockups. Run the app first, then point this at it:

    uvicorn chainlit_app.server:app --port 7880
    python scripts/capture_app_screens.py --base http://127.0.0.1:7880

Output: public/shots/*.png
"""

import argparse
import os

from playwright.sync_api import sync_playwright

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "shots")

# (filename, category tab, starter question, text that proves the answer rendered)
SHOTS = [
    ("starters.png", None, None, None),
    (
        "stat.png",
        "Revenue and growth",
        "What was our total MRR in June 2026?",
        "$4,124,",
    ),
    (
        "table.png",
        "Customers and segments",
        "Which customers are at risk?",
        "total rows",
    ),
    (
        "refusal.png",
        "Guardrail checks",
        "Was churn anomalous in January 2025?",
        "No matching data",
    ),
]


def capture(base_url: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    chat_url = base_url.rstrip("/") + "/chat/"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        # Tall enough that a full answer fits without Chainlit's autoscroll
        # cropping the question off the top.
        ctx = browser.new_context(
            viewport={"width": 940, "height": 1000}, device_scale_factor=2
        )
        page = ctx.new_page()

        for name, category, question, marker in SHOTS:
            page.goto(chat_url, wait_until="networkidle")
            # Wait for Chainlit to mount and the starters to appear.
            page.wait_for_selector("text=Revenue and growth", timeout=60_000)
            page.wait_for_timeout(1200)

            if category:
                page.click(f"button:has-text('{category}')")
                page.wait_for_timeout(500)
                page.click(f"button:has-text(\"{question}\")")
                # Cortex Analyst plus a Snowflake round trip.
                page.wait_for_function(
                    "m => document.body.innerText.includes(m)",
                    arg=marker,
                    timeout=120_000,
                )
                page.wait_for_timeout(1500)
                # Chainlit pins the view to the newest message; wind every
                # scrollable container back so the question stays visible.
                page.evaluate(
                    "document.querySelectorAll('*').forEach(el => {"
                    "  if (el.scrollHeight > el.clientHeight + 8) el.scrollTop = 0;"
                    "})"
                )
                page.wait_for_timeout(600)

            out = os.path.join(OUT_DIR, name)
            page.screenshot(path=out)
            print("wrote", os.path.abspath(out))

        browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:7880")
    args = ap.parse_args()
    capture(args.base)
